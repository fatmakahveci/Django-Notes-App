from django import template

from blog_app.text import plain_text

register = template.Library()
# Keep autoescaping enabled: decoded entities can contain literal HTML characters.
register.filter("note_text", plain_text)
