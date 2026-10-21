from django import forms
from django.forms import ModelForm
from .models import *
from .models import Task, Category, UserProfile
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .tones import TONES, tone_choices


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

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


# datetime-local inputs need "YYYY-MM-DDTHH:MM", not Django's default format.
# Without this the edit page shows blank dates and saving wipes them.
DATETIME_LOCAL_FORMAT = '%Y-%m-%dT%H:%M'
DATETIME_LOCAL_INPUTS = ['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S']

# Built-in sounds (grouped) plus "upload your own". See tasks/tones.py
ALARM_TONE_CHOICES = tone_choices() + [('Your own', [('custom', 'Upload your own sound')])]


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        # 'complete' is left out on purpose: ticking happens on the list, and
        # leaving it here un-ticked completed tasks every time they were edited.
        fields = ['title', 'description','due_date','priority', 'categories',  'is_recurring', 'recurring_frequency', 'recurring_interval',
        'alarm_enabled',    
        'alarm_time',   
        'alarm_tone',
        'wake_check']
        widgets = {
            'categories': forms.CheckboxSelectMultiple(attrs={'class': 'chip-input'}),
            'description' : forms.Textarea(attrs={
                'rows': 3,
                'placeholder' : 'Anything that will help future you (optional)',
            }),
            'due_date' : forms.DateTimeInput(format=DATETIME_LOCAL_FORMAT, attrs= {
                'type' : 'datetime-local',
                'class' : 'form-input',
            }),
            'priority' : forms.RadioSelect(attrs={'class': 'seg-input'}),
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Call mum, pay electricity bill',
                'autocomplete': 'off',
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
            'alarm_time': forms.DateTimeInput(format=DATETIME_LOCAL_FORMAT, attrs={
                'class': 'form-input',
                'type': 'datetime-local',
                'id': 'id_alarm_time'
            }),
            'alarm_tone': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_alarm_tone'
            }),
            'wake_check': forms.CheckboxInput(attrs={'id': 'id_wake_check'}),

            
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
        
        self.fields['description'].widget.attrs.update({'class': 'form-textarea'})
        self.fields['categories'].required = False
        self.fields['categories'].label = 'Categories'
        self.fields['description'].required = False
        self.fields['due_date'].required = False
        self.fields['due_date'].label = 'Due'
        self.fields['priority'].label = 'Priority'
        # Category colours, so the template can colour each chip
        self.category_colors = {c.pk: c.color for c in Category.objects.all()}


        self.fields['due_date'].input_formats = DATETIME_LOCAL_INPUTS
        self.fields['alarm_time'].input_formats = DATETIME_LOCAL_INPUTS
        self.fields['alarm_time'].required = False

        # Keep a previously uploaded custom tone selectable when editing
        choices = list(ALARM_TONE_CHOICES)
        current_tone = getattr(self.instance, 'alarm_tone', '') or ''
        if current_tone.startswith(('/', 'http')):
            choices.insert(0, (current_tone, 'My uploaded sound'))
        self.fields['alarm_tone'].widget.choices = choices
        self.fields['alarm_tone'].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('alarm_enabled') and not cleaned.get('alarm_time'):
            # Default the alarm to the due date if only a due date was set
            if cleaned.get('due_date'):
                cleaned['alarm_time'] = cleaned['due_date']
            else:
                # Nothing to ring for yet: quietly leave the alarm off
                cleaned['alarm_enabled'] = False
        tone = cleaned.get('alarm_tone') or ''
        if not (tone in TONES or tone == 'custom' or tone.startswith(('/', 'http'))):
            cleaned['alarm_tone'] = 'classic'
        if cleaned.get('recurring_frequency') and cleaned['recurring_frequency'] != 'none':
            cleaned['is_recurring'] = True
        if cleaned.get('is_recurring') and (cleaned.get('recurring_frequency') or 'none') == 'none':
            cleaned['recurring_frequency'] = 'daily'
        if cleaned.get('is_recurring') and not cleaned.get('due_date'):
            # Repeats need a start: begin tomorrow at 9 AM
            from datetime import datetime, time as dtime, timedelta as td
            from django.utils import timezone as tz
            start = tz.localdate() + td(days=1)
            cleaned['due_date'] = tz.make_aware(datetime.combine(start, dtime(9, 0)))
        return cleaned




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

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Another account already uses this email.')
        return email


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
        ]
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={'class': 'toggle-checkbox'}),
            'email_daily_summary': forms.CheckboxInput(attrs={'class': 'toggle-checkbox'}),
            'email_task_reminders': forms.CheckboxInput(attrs={'class': 'toggle-checkbox'}),
            'browser_notifications': forms.CheckboxInput(attrs={'class': 'toggle-checkbox'}),
        }
        labels = {
            'email_notifications': 'Emails from Quantum Manager',
            'email_daily_summary': 'Morning summary',
            'email_task_reminders': 'Email me when an alarm rings',
            'browser_notifications': 'Browser Notifications',
        }
        help_texts = {
            'email_notifications': 'Turn this off to stop all reminder and summary emails',
            'email_daily_summary': 'At 7 AM, an email with what is due today and anything overdue',
            'email_task_reminders': 'A backup for your alarms, in case your phone is off',
            'browser_notifications': '',
        }


class AppearanceSettingsForm(forms.ModelForm):
    """Form for theme and appearance"""
    
    class Meta:
        model = UserProfile
        fields = ['theme', 'date_format']
        widgets = {
            'theme': forms.RadioSelect(attrs={'class': 'theme-input'}),
            'date_format': forms.Select(choices=[
                ('DD/MM/YYYY', '17/10/2026 (day first)'),
                ('MM/DD/YYYY', '10/17/2026 (month first)'),
                ('YYYY-MM-DD', '2026-10-17 (year first)'),
            ], attrs={'class': 'form-select'}),
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
        fields = [
            'alarm_enabled', 'alarm_minutes_before', 'default_alarm_tone',
            'default_priority', 'default_category', 'tasks_per_page',
        ]
        widgets = {
            'alarm_enabled': forms.CheckboxInput(attrs={'class': 'toggle-checkbox'}),
            'alarm_minutes_before': forms.Select(choices=[
                (0, 'At the due time'), (5, '5 minutes before'), (15, '15 minutes before'),
                (30, '30 minutes before'), (60, '1 hour before'), (1440, '1 day before'),
            ], attrs={'class': 'form-select'}),
            'default_alarm_tone': forms.Select(choices=tone_choices(), attrs={'class': 'form-select', 'data-tone-select': ''}),
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
            'alarm_enabled': 'Remind me when a task is due',
            'alarm_minutes_before': 'When to remind me',
            'default_alarm_tone': 'Alarm sound',
            'default_priority': 'Priority',
            'default_category': 'Category',
            'tasks_per_page': 'Tasks per page',
        }
        help_texts = {
            'alarm_enabled': 'New tasks with a due date get an alarm automatically. You can still turn it off per task.',
            'alarm_minutes_before': '',
            'default_alarm_tone': '',
            'default_priority': 'Pre-selected when you create a task',
            'default_category': 'Pre-selected when you create a task',
            'tasks_per_page': 'How many tasks to show before "Next page" (5 to 100)',
        }

    def clean_tasks_per_page(self):
        return max(5, min(100, self.cleaned_data['tasks_per_page'] or 20))

    def clean_alarm_minutes_before(self):
        return max(0, min(10080, int(self.cleaned_data['alarm_minutes_before'] or 0)))


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
            'show_email': 'Show my email',
            'allow_shared_lists': 'Shared lists',
        }
        help_texts = {
            'show_email': 'People in your shared lists can see your email',
            'allow_shared_lists': 'Let people add you to their shared lists',
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
            'category': forms.RadioSelect(attrs={'class': 'chip-input'}),
            'color': forms.RadioSelect(attrs={'class': 'swatch-input'}),
            'tags': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'birthday, important, inspiration (comma-separated)'
            }),
            'is_pinned': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            })
        }
