from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from tinymce.widgets import TinyMCE

from .models import Post, Tag
from .text import plain_text, normalize_search


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs["class"] = "category-choices"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"


class LoginForm(StyledFormMixin, AuthenticationForm):
    pass


class SignupForm(StyledFormMixin, UserCreationForm):
    pass


def tag_names(value):
    names = list(dict.fromkeys(normalize_search(name) for name in value.split(",") if name.strip()))
    if len(names) > 12 or any(len(name) > 32 for name in names):
        raise ValidationError("Use up to 12 tags, each at most 32 characters.")
    return names


class PostForm(StyledFormMixin, ModelForm):
    personal_tags = forms.CharField(required=False, max_length=400, label="Personal tags",
        help_text="Separate tags with commas. Only you see these labels.")
    visibility = forms.ChoiceField(
        choices=[("published", "Published — public"), ("draft", "Draft — private")],
        required=False,
        help_text="Drafts are visible only to you and administrators. You can publish them later.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visibility"].initial = "published" if self.instance.is_published else "draft"
        if self.instance.pk and "personal_tags" not in self.initial:
            self.initial["personal_tags"] = ", ".join(self.instance.tags.values_list("name", flat=True))

    class Meta:
        model = Post
        fields = ["title", "content", "categories", "visibility"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Give your note a title"}),
            "content": TinyMCE(mce_attrs={
                "height": 380,
                "menubar": False,
                "toolbar": "undo redo | blocks | bold italic | bullist numlist | link | removeformat",
                "content_style": "body { font-family: system-ui, sans-serif; color: #263c34; font-size: 16px; line-height: 1.7; padding: 8px 12px; }",
            }),
            "categories": forms.CheckboxSelectMultiple(),
        }
        help_texts = {"categories": "Choose any that fit your note, or leave them unchecked."}

    def clean_personal_tags(self):
        return tag_names(self.cleaned_data["personal_tags"])

    def _save_m2m(self):
        super()._save_m2m()
        tags = [Tag.objects.get_or_create(owner=self.instance.author.user, name=name)[0]
                for name in self.cleaned_data.get("personal_tags", [])]
        self.instance.tags.set(tags)

    def clean_visibility(self):
        return self.cleaned_data["visibility"] or ("published" if self.instance.is_published else "draft")

    def save(self, commit=True):
        self.instance.is_published = self.cleaned_data["visibility"] == "published"
        return super().save(commit=commit)

    def clean_content(self):
        content = self.cleaned_data["content"]
        # Ignore invisible characters only for the emptiness check. Keep the
        # original text intact, including joiners used in emoji and other scripts.
        if len(content.encode("utf-8")) > 200_000:
            raise ValidationError("Keep each note below 200 KB.")
        visible = plain_text(content).translate(dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff")))
        if not visible.strip():
            raise ValidationError("Write some text before saving your note.")
        return content


class SearchFilters(forms.Form):
    after = forms.DateField(required=False, label="Created on or after", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    before = forms.DateField(required=False, label="Created on or before", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))

    def clean(self):
        data = super().clean()
        if data.get("after") and data.get("before") and data["after"] > data["before"]:
            raise ValidationError("The start date must be on or before the end date.")
        return data
