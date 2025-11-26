from django import forms
from django.forms import ModelForm
from .models import *
from .models import Task, Category
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


# Create your forms here.
class CustomUserForm(UserCreationForm):
    email = forms.EmailField(required=True)
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        #add custom styling to form fields
        for fieldName in self.fields:
            self.fields[fieldName].widget.attrs.update({
                'class': 'form-input',
                'placeholder': self.fields[fieldName].label
            })
        
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'complete', 'categories']
        widgets = {
            'categories': forms.SelectMultiple(attrs={'class': 'category-select', 'multiple': True, 'size': 1}),
        } 
        
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        #add custom styling to form fields
        for fieldName in self.fields:
            self.fields[fieldName].widget.attrs.update({
                'class': 'form-input',
                'placeholder': "Enter task"
            })
        
        #customize the complete field
        self.fields['categories'].widget.attrs.update({
            'class': 'category-select','multiple': True, 'size': 1
        })
        # make categories field optional
        self.fields['categories'].required = False
        self.fields['categories'].label = "Categories (hold Ctrl or Cmd to select multiple)"



