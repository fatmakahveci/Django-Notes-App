from django import template

from blog_app.text import plain_text

register = template.Library()
register.filter("note_text", plain_text)
