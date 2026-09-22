from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from tinymce.widgets import TinyMCE

from .models import Post
from .text import plain_text


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


class PostForm(StyledFormMixin, ModelForm):
    class Meta:
        model = Post
        fields = ["title", "content", "categories"]
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

    def clean_content(self):
        content = self.cleaned_data["content"]
        visible = plain_text(content).translate(dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff")))
        if not visible.strip():
            raise ValidationError("Write some text before saving your note.")
        return content
