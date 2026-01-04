from django import forms
from django.forms import ModelForm
from .models import *
from .models import Task, Category, UserProfile
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
        fields = ['title', 'description','due_date','priority','complete', 'categories',  'is_recurring', 'recurring_frequency', 'recurring_interval',
        'alarm_enabled',    
        'alarm_time',   
        'alarm_tone']
        widgets = {
            'categories': forms.SelectMultiple(attrs={'class': 'category-select', 'multiple': True, 'size': 1}),
            'description' : forms.Textarea(attrs={
                'rows': 3,
                'placeholder' : 'Add details about this task (optional)...'
            }),
            'due_date' : forms.DateTimeInput(attrs= {
                'type' : 'datetime-local',
                'class' : 'form-input',
            }),
            'priority' : forms.Select(attrs={
                'class' : 'form-select'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Call dentist, Buy groceries, Finish report...',
            }),
            'is_recurring': forms.CheckboxInput(attrs={
                'class': 'toggle-checkbox',
                'id': 'id_is_recurring'
            }),
            'recurring_frequency': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_recurring_frequency'
            }),
            'recurring_interval': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': 1,
                'placeholder': 'Number of days',
                'id': 'id_recurring_interval'
            }),
            'alarm_enabled': forms.CheckboxInput(attrs={
                'class': 'toggle-checkbox',
                'id': 'id_alarm_enabled'
            }),
            'alarm_time': forms.DateTimeInput(attrs={
                'class': 'form-input',
                'type': 'datetime-local',
                'id': 'id_alarm_time'
            }),
            'alarm_tone': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_alarm_tone'
            }),

            
        }
        labels = {
            'is_recurring': 'Make this a recurring task',
            'recurring_frequency': 'Repeat',
            'recurring_interval': 'Every (days)',
            
            'alarm_enabled': 'Enable Alarm',
            'alarm_time': 'Alarm Time',
            'alarm_tone': 'Alarm Sound',
        }
        help_texts = {
            'is_recurring': 'Task will automatically recreate when completed',
            'recurring_frequency': 'How often should this task repeat?',
            'recurring_interval': 'For custom frequency only',
            
            'alarm_enabled': 'Get notified when this task is due',
            'alarm_time': 'When should the alarm ring?',
            'alarm_tone': 'Choose your alarm sound',
        }
        
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        #add custom styling to form fields
        
        self.fields['title'].widget.attrs.update({
                'class': 'form-input',
                'placeholder': "Enter task"
            })
        #style the description field
        self.fields['description'].widget.attrs.update({
            'class' : 'form-textarea',
        })
        self.fields['complete'].widget.attrs.update({
            'class': 'complete',
        })
        #customize the complete field
        self.fields['categories'].widget.attrs.update({
            'class': 'category-select','multiple': True, 'size': 1
        })
        
        # make categories field optional
        self.fields['categories'].required = False
        self.fields['categories'].label = "Categories (hold Ctrl or Cmd to select multiple)"
        self.fields['description'].required = False 
        self.fields['due_date'].required = False
        
        #labels
        self.fields['due_date'].label = 'Due Date'
        self.fields['priority'].label = 'Priority'


        self.fields['alarm_tone'].choices = [
            ('classic', '⏰ Classic Alarm'),
            ('chime', '🎵 Soft Chime'),
            ('urgent', '🚨 Urgent Alert'),
            ('custom', '📁 Upload Custom (coming soon)'),
        ]




class UserUpdateForm(forms.ModelForm):
    """Form for updating User model fields (username, email)"""
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Username'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Email address'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'First name (optional)'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Last name (optional)'
            }),
        }


class ProfileUpdateForm(forms.ModelForm):
    """Form for updating UserProfile model fields (avatar, bio)"""
    
    class Meta:
        model = UserProfile
        fields = ['avatar', 'bio']
        widgets = {
            'bio': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'Tell us about yourself... (optional)',
                'rows': 4,
                'maxlength': 500
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['avatar'].widget.attrs.update({
            'class': 'file-input',
            'accept': 'image/*'
        })


class PasswordChangeForm(forms.Form):
    """Form for changing password from profile page"""
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Current password'
        }),
        label='Current Password'
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'New password'
        }),
        label='New Password',
        min_length=8
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirm new password'
        }),
        label='Confirm New Password',
        min_length=8
    )
    
    def clean_new_password2(self):
        """Check that new passwords match"""
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match!")
        return password2
    

class NotificationSettingsForm(forms.ModelForm):
    """Form for notification preferences"""
    
    class Meta:
        model = UserProfile
        fields = [
            'email_notifications',
            'email_daily_summary',
            'email_task_reminders',
            'browser_notifications'
        ]
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={'class': 'toggle-checkbox'}),
            'email_daily_summary': forms.CheckboxInput(attrs={'class': 'toggle-checkbox'}),
            'email_task_reminders': forms.CheckboxInput(attrs={'class': 'toggle-checkbox'}),
            'browser_notifications': forms.CheckboxInput(attrs={'class': 'toggle-checkbox'}),
        }
        labels = {
            'email_notifications': 'Enable Email Notifications',
            'email_daily_summary': 'Daily Summary Email',
            'email_task_reminders': 'Task Reminder Emails',
            'browser_notifications': 'Browser Notifications',
        }
        help_texts = {
            'email_notifications': 'Master switch for all email notifications',
            'email_daily_summary': 'Receive a daily email with your pending tasks',
            'email_task_reminders': 'Get reminders before tasks are due',
            'browser_notifications': 'Enable desktop notifications (requires permission)',
        }


class AppearanceSettingsForm(forms.ModelForm):
    """Form for theme and appearance"""
    
    class Meta:
        model = UserProfile
        fields = ['theme', 'date_format']
        widgets = {
            'theme': forms.RadioSelect(attrs={'class': 'radio-buttons'}),
            'date_format': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'theme': 'Theme',
            'date_format': 'Date Format',
        }
        help_texts = {
            'theme': 'Choose your preferred color scheme',
            'date_format': 'How dates should be displayed',
        }


class TaskDefaultsForm(forms.ModelForm):
    """Form for default task settings"""
    
    class Meta:
        model = UserProfile
        fields = ['default_priority', 'default_category', 'tasks_per_page']
        widgets = {
            'default_priority': forms.Select(attrs={'class': 'form-select'}),
            'default_category': forms.Select(attrs={'class': 'form-select'}),
            'tasks_per_page': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': 5,
                'max': 100,
                'step': 5
            }),
        }
        labels = {
            'default_priority': 'Default Priority',
            'default_category': 'Default Category',
            'tasks_per_page': 'Tasks Per Page',
        }
        help_texts = {
            'default_priority': 'Pre-selected priority when creating tasks',
            'default_category': 'Pre-selected category when creating tasks',
            'tasks_per_page': 'Number of tasks to show per page (5-100)',
        }


class PrivacySettingsForm(forms.ModelForm):
    """Form for privacy settings"""
    
    class Meta:
        model = UserProfile
        fields = ['show_email', 'allow_shared_lists']
        widgets = {
            'show_email': forms.CheckboxInput(attrs={'class': 'toggle-checkbox'}),
            'allow_shared_lists': forms.CheckboxInput(attrs={'class': 'toggle-checkbox'}),
        }
        labels = {
            'show_email': 'Show Email Publicly',
            'allow_shared_lists': 'Allow Shared Lists',
        }
        help_texts = {
            'show_email': 'Make your email visible to other users',
            'allow_shared_lists': 'Enable collaboration features',
        }
        

class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['title', 'content', 'category', 'color', 'tags', 'is_pinned']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Give your note a title...'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 6,
                'placeholder': 'Write your thoughts, memories, or ideas here...'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'color': forms.Select(attrs={
                'class': 'form-select'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'birthday, important, inspiration (comma-separated)'
            }),
            'is_pinned': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            })
        }