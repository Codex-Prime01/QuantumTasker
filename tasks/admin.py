from django.contrib import admin
from .models import Task, Category
# Register your models here.

from .models import *


class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'color']
    list_editable = ['color']
    
admin.site.register(Task) 
admin.site.register(Category, CategoryAdmin)