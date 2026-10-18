from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from datetime import timedelta

# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#00f5ff')
    
    class Meta:
        verbose_name_plural = 'Categories' #correct plural in admin
        
    def __str__(self):
        return self.name
    

class Task(models.Model):
    
    
    #priority choices
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
        
    ]
    
    RECURRING_CHOICES = [
        ('none', 'Does Not Repeat'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Every 2 Weeks'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom'),
    ]
    
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    complete = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=10,choices=PRIORITY_CHOICES,default='medium')
    
    categories = models.ManyToManyField(Category, blank=True)
        
     
    is_recurring = models.BooleanField(default=False)
    recurring_frequency = models.CharField(
        max_length=20,
        choices=RECURRING_CHOICES,
        default='none'
    )
    recurring_interval = models.IntegerField(default=1, help_text="For custom frequency")
    parent_task = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='occurrences',
        help_text="Original recurring task"
    )
    completed_date = models.DateTimeField(null=True, blank=True)
     
    alarm_enabled = models.BooleanField(default=False)
    alarm_time = models.DateTimeField(null=True, blank=True, help_text="When to trigger alarm")
    alarm_tone = models.CharField(max_length=500, default='classic', help_text="Built-in tone name or URL of an uploaded sound")
    alarm_snoozed_until = models.DateTimeField(null=True, blank=True)
    alarm_dismissed = models.BooleanField(default=False)
    # The ring time we last sent a push/email for, so each ring is sent once
    last_reminded_ring = models.DateTimeField(null=True, blank=True)

    # Guards so ticking a task on/off can't farm points or spawn duplicate repeats
    points_awarded = models.BooleanField(default=False)
    next_occurrence_created = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    @property
    def ring_at(self):
        """When the alarm should ring next (snooze wins over the original time)."""
        return self.alarm_snoozed_until or self.alarm_time

    @property
    def is_overdue(self): #new helper method
        #to check if task is overdue    
        if self.due_date and not self.complete:
            return timezone.now() > self.due_date
        return False

    
    def create_next_occurrence(self):
        """Create the next occurrence of this recurring task"""
        if not self.is_recurring or self.recurring_frequency == 'none':
            return None
        if self.next_occurrence_created:
            return None  # already spawned once, don't make duplicates

        next_due_date = self.calculate_next_due_date()
        if not next_due_date:
            return None

        # Keep the alarm the same distance before the due date as the original
        next_alarm_time = None
        if self.alarm_enabled and self.alarm_time:
            next_alarm_time = next_due_date - (self.due_date - self.alarm_time)

        next_task = Task.objects.create(
            user=self.user,
            title=self.title,
            description=self.description,
            due_date=next_due_date,
            priority=self.priority,
            is_recurring=True,
            recurring_frequency=self.recurring_frequency,
            recurring_interval=self.recurring_interval,
            parent_task=self.parent_task or self,
            alarm_enabled=self.alarm_enabled and next_alarm_time is not None,
            alarm_time=next_alarm_time,
            alarm_tone=self.alarm_tone,
        )
        next_task.categories.set(self.categories.all())

        self.next_occurrence_created = True
        self.save(update_fields=['next_occurrence_created'])
        return next_task

    def _step(self, dt):
        """Move a datetime forward by one repeat period."""
        freq = self.recurring_frequency
        if freq == 'daily':
            return dt + timedelta(days=1)
        if freq == 'weekly':
            return dt + timedelta(weeks=1)
        if freq == 'biweekly':
            return dt + timedelta(weeks=2)
        if freq == 'custom':
            return dt + timedelta(days=max(1, self.recurring_interval))
        if freq in ('monthly', 'yearly'):
            months = 1 if freq == 'monthly' else 12
            month_index = dt.month - 1 + months
            year = dt.year + month_index // 12
            month = month_index % 12 + 1
            # Clamp the day (e.g. Jan 31 -> Feb 28)
            for day in (dt.day, 30, 29, 28):
                try:
                    return dt.replace(year=year, month=month, day=day)
                except ValueError:
                    continue
        return None

    def calculate_next_due_date(self):
        """Next due date after the current one that is still in the future."""
        if not self.due_date:
            return None
        next_date = self._step(self.due_date)
        now = timezone.now()
        # If the task was done very late, skip ahead past missed periods
        guard = 0
        while next_date is not None and next_date <= now and guard < 1000:
            next_date = self._step(next_date)
            guard += 1
        return next_date
    
    def get_recurring_info(self):
        """Return human-readable recurring info"""
        if not self.is_recurring or self.recurring_frequency == 'none':
            return None
        
        frequency_map = {
            'daily': '🔄 Repeats daily',
            'weekly': '🔄 Repeats weekly',
            'biweekly': '🔄 Repeats every 2 weeks',
            'monthly': '🔄 Repeats monthly',
            'yearly': '🔄 Repeats yearly',
            'custom': f'🔄 Repeats every {self.recurring_interval} days',
        }
        
        return frequency_map.get(self.recurring_frequency, '🔄 Recurring')
    
    class Meta:
        ordering = ['-created']
        

class TaskTemplate(models.Model):
    """Template for creating multiple tasks at once"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=10, default='📋')
    is_default = models.BooleanField(default=False)  # System templates
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    def instantiate(self, user):
        """Create all tasks from this template for the user"""
        created_tasks = []
        
        for template_item in self.items.all():
            task = Task.objects.create(
                user=user,
                title=template_item.title,
                description=template_item.description,
                priority=template_item.priority,
                is_recurring=template_item.is_recurring,
                recurring_frequency=template_item.recurring_frequency,
            )
            
            # Copy categories if any
            if template_item.categories.exists():
                task.categories.set(template_item.categories.all())
            
            created_tasks.append(task)
        
        return created_tasks
    
    class Meta:
        ordering = ['-created']


class TemplateItem(models.Model):
    """Individual task within a template"""
    template = models.ForeignKey(TaskTemplate, on_delete=models.CASCADE, related_name='items')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    priority = models.CharField(
        max_length=10,
        choices=Task.PRIORITY_CHOICES,
        default='medium'
    )
    categories = models.ManyToManyField(Category, blank=True)
    is_recurring = models.BooleanField(default=False)
    recurring_frequency = models.CharField(
        max_length=20,
        choices=Task.RECURRING_CHOICES,
        default='none'
    )
    order = models.IntegerField(default=0)  # For sorting items
    
    def __str__(self):
        return f"{self.template.name} - {self.title}"
    
    class Meta:
        ordering = ['order', 'id']


    
class UserProfile(models.Model):
    """Extended user profile for additional info"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    email_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    verification_token_created = models.DateTimeField(default=timezone.now)
    
    
    reset_token = models.UUIDField(default=uuid.uuid4, editable=False)
    reset_token_created = models.DateTimeField(null=True, blank=True)
    
    
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    
    
    email_notifications = models.BooleanField(default=True)
    email_daily_summary = models.BooleanField(default=False)
    email_task_reminders = models.BooleanField(default=False)
    browser_notifications = models.BooleanField(default=False)

    # Reminder defaults: new tasks with a due date get an alarm automatically
    alarm_enabled = models.BooleanField(default=True)
    default_alarm_tone = models.CharField(max_length=200, default='classic')
    alarm_minutes_before = models.IntegerField(default=0, help_text="Minutes before due date to alarm")

    # The user's timezone (from their browser), used for daily summary emails
    timezone = models.CharField(max_length=64, blank=True, default='')
    last_summary_date = models.DateField(null=True, blank=True)

    THEME_CHOICES = [
        ('blue', 'Blue'),
        ('light', 'White'),
        ('dark', 'Dark'),
        ('auto', 'Match my device'),
    ]
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='blue')
    
    # Default Task Settings
    default_priority = models.CharField(
        max_length=10,
        choices=Task.PRIORITY_CHOICES,
        default='medium'
    )
    default_category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='default_for_users'
    )
    
    # Privacy Settings
    show_email = models.BooleanField(default=False)
    allow_shared_lists = models.BooleanField(default=True)
    
    # App Settings
    tasks_per_page = models.IntegerField(default=20)
    date_format = models.CharField(
        max_length=20,
        choices=[
            ('MM/DD/YYYY', 'MM/DD/YYYY (US)'),
            ('DD/MM/YYYY', 'DD/MM/YYYY (EU)'),
            ('YYYY-MM-DD', 'YYYY-MM-DD (ISO)'),
        ],
        default='DD/MM/YYYY'
    )
    
    
    def __str__(self):
        return f"{self.user.username}'s profile"
    
    def is_verification_token_valid(self):
        """Verification links work for 24 hours."""
        if not self.verification_token_created:
            return False
        return timezone.now() < self.verification_token_created + timedelta(hours=24)

    def is_reset_token_valid(self):
        """Password reset links work for 1 hour, and only once."""
        if not self.reset_token_created:
            return False
        return timezone.now() < self.reset_token_created + timedelta(hours=1)


    def get_avatar_url(self):
        
        """Return avatar URL or None if not set"""
        if self.avatar:
            # Check if file actually exists
            try:
                if self.avatar.storage.exists(self.avatar.name):
                    return self.avatar.url
            except Exception:
                return None
        return None
    
    def get_or_create_stats(self):
        """Get or create user stats"""
        stats, created = UserStats.objects.get_or_create(user=self.user)
        return stats


class Achievement(models.Model):
    """Achievements users can unlock"""
    ACHIEVEMENT_TYPES = [
        ('tasks_completed', 'Tasks Completed'),
        ('streak', 'Streak'),
        ('category', 'Category Master'),
        ('speed', 'Speed'),
        ('consistency', 'Consistency'),
        ('special', 'Special'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=10, default='🏆')
    achievement_type = models.CharField(max_length=20, choices=ACHIEVEMENT_TYPES)
    requirement = models.IntegerField(help_text="Number needed to unlock")
    points = models.IntegerField(default=10)
    is_hidden = models.BooleanField(default=False, help_text="Hidden until unlocked")
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['requirement']


class UserAchievement(models.Model):
    """Track which achievements users have unlocked"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    unlocked_at = models.DateTimeField(auto_now_add=True)
    progress = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['user', 'achievement']
        ordering = ['-unlocked_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.achievement.name}"


class UserStats(models.Model):
    """Track user statistics for achievements and gamification"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='stats')
    
    # Streak tracking
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_completion_date = models.DateField(null=True, blank=True)
    
    # Task stats
    total_tasks_completed = models.IntegerField(default=0)
    tasks_completed_today = models.IntegerField(default=0)
    
    # Points
    total_points = models.IntegerField(default=0)
    
    # Dates
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s stats"
    
    def update_streak(self):
        """Update streak when a task is completed"""
        today = timezone.localdate()  # the user's day, not the server's

        if self.last_completion_date != today:
            self.tasks_completed_today = 0

        # First completion ever
        if not self.last_completion_date:
            self.current_streak = 1
            self.longest_streak = 1
            self.last_completion_date = today
            self.save()
            return
        
        # Already completed task today
        if self.last_completion_date == today:
            return
        
        # Completed yesterday - continue streak
        yesterday = today - timedelta(days=1)
        if self.last_completion_date == yesterday:
            self.current_streak += 1
            if self.current_streak > self.longest_streak:
                self.longest_streak = self.current_streak
        # Missed a day - reset streak
        else:
            self.current_streak = 1
        
        self.last_completion_date = today
        self.save()
    
    def add_points(self, points):
        """Add points to user's total"""
        self.total_points += points
        self.save()
    
    def check_achievements(self):
        """Check if user unlocked any new achievements"""
        from django.db.models import Q
        
        unlocked = []
        
        # Get all achievements user hasn't unlocked yet
        unlocked_achievement_ids = UserAchievement.objects.filter(
            user=self.user
        ).values_list('achievement_id', flat=True)
        
        available_achievements = Achievement.objects.exclude(
            id__in=unlocked_achievement_ids
        )
        
        for achievement in available_achievements:
            should_unlock = False
            
            # Check based on achievement type
            if achievement.achievement_type == 'tasks_completed':
                if self.total_tasks_completed >= achievement.requirement:
                    should_unlock = True
            
            elif achievement.achievement_type == 'streak':
                if self.current_streak >= achievement.requirement:
                    should_unlock = True
            
            elif achievement.achievement_type == 'consistency':
                # Check if user completed tasks on consecutive days
                if self.longest_streak >= achievement.requirement:
                    should_unlock = True
            
            # Unlock if criteria met
            if should_unlock:
                user_achievement = UserAchievement.objects.create(
                    user=self.user,
                    achievement=achievement,
                    progress=100
                )
                self.add_points(achievement.points)
                unlocked.append(achievement)
        
        return unlocked



class Note(models.Model):
    """Quick notes and memories - not full tasks"""
    
    CATEGORY_CHOICES = [
        ('personal', '👤 Personal'),
        ('ideas', '💡 Ideas'),
        ('dates', '📅 Important Dates'),
        ('quotes', '💬 Quotes'),
        ('reference', '📚 Reference'),
        ('other', '🔖 Other'),
    ]
    
    COLOR_CHOICES = [
        ('#FFD700', '🟡 Yellow'),
        ('#FF69B4', '🔴 Pink'),
        ('#87CEEB', '🔵 Blue'),
        ('#98FB98', '🟢 Green'),
        ('#DDA0DD', '🟣 Purple'),
        ('#FFB6C1', '🟠 Coral'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    title = models.CharField(max_length=200)
    content = models.TextField(help_text="Write your note, memory, or idea here")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='personal')
    color = models.CharField(max_length=7, choices=COLOR_CHOICES, default='#FFD700')
    
    is_pinned = models.BooleanField(default=False, help_text="Pin to top")
    is_archived = models.BooleanField(default=False)
    
    tags = models.CharField(max_length=200, blank=True, help_text="Comma-separated tags")
    
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_pinned', '-created']
    
    def __str__(self):
        return self.title
    
    def get_tags_list(self):
        """Return tags as a list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []


class PushSubscription(models.Model):
    """A browser/device that agreed to receive push alarms."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.URLField(max_length=1000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.user_agent[:40] or 'device'}"

    def as_webpush_info(self):
        return {'endpoint': self.endpoint, 'keys': {'p256dh': self.p256dh, 'auth': self.auth}}
