from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.forms import ModelForm

from .models import Post
from .text import plain_text


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
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

    def clean_content(self):
        content = self.cleaned_data["content"]
        visible = plain_text(content).translate(dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff")))
        if not visible.strip():
            raise ValidationError("Write some text before saving your note.")
        return content
