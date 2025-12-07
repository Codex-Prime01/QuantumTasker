from django.contrib import admin
from .models import Task, Category
# Register your models here.

from .models import *

#customises the admin interfaces
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'color']
    list_editable = ['color'] #allows to edit colors directly
    
admin.site.register(Task) 
admin.site.register(Category, CategoryAdmin)