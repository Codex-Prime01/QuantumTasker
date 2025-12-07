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
     
    def __str__(self):
        return self.title
        return self.title
    
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
        
        # Calculate next due date
        next_due_date = self.calculate_next_due_date()
        
        if not next_due_date:
            return None
        
        # Create new task instance
        next_task = Task.objects.create(
            user=self.user,
            title=self.title,
            description=self.description,
            due_date=next_due_date,
            priority=self.priority,
            is_recurring=True,
            recurring_frequency=self.recurring_frequency,
            recurring_interval=self.recurring_interval,
            parent_task=self.parent_task or self,  # Link to original parent
        )
        
        # Copy categories
        next_task.categories.set(self.categories.all())
        
        return next_task
    
    def calculate_next_due_date(self):
        """Calculate the next due date based on frequency"""
        if not self.due_date:
            return None
        
        base_date = self.completed_date or timezone.now()
        
        if self.recurring_frequency == 'daily':
            return base_date + timedelta(days=1)
        
        elif self.recurring_frequency == 'weekly':
            return base_date + timedelta(weeks=1)
        
        elif self.recurring_frequency == 'biweekly':
            return base_date + timedelta(weeks=2)
        
        elif self.recurring_frequency == 'monthly':
            # Add one month (approximately 30 days, adjust for month boundaries)
            return base_date + timedelta(days=30)
        
        elif self.recurring_frequency == 'yearly':
            return base_date + timedelta(days=365)
        
        elif self.recurring_frequency == 'custom':
            return base_date + timedelta(days=self.recurring_interval)
        
        return None
    
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
    verification_token_created = models.DateTimeField(auto_now_add=True)
    
    
    reset_token = models.UUIDField(default=uuid.uuid4, editable=False)
    reset_token_created = models.DateTimeField(null=True, blank=True)
    
    
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    
    
    email_notifications = models.BooleanField(default=True)
    email_daily_summary = models.BooleanField(default=True)
    email_task_reminders = models.BooleanField(default=True)
    browser_notifications = models.BooleanField(default=False)
    
    
     # Theme Settings
    theme = models.CharField(
        max_length=10,
        choices=[('light', 'Light'), ('dark', 'Dark'), ('auto', 'Auto')],
        default='dark'
    )
    
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
        default='MM/DD/YYYY'
    )
    
    
    def __str__(self):
        return f"{self.user.username}'s profile"
    
    def is_verification_token_valid(self):
        """Check if verification token is still valid (24 hours)"""
        from datetime import timedelta
        expiry_time = self.verification_token_created + timedelta(hours=24)
        return timezone.now() < expiry_time
    
    def is_reset_token_valid(self):
        #check if reset token is still valid (1 hour)
        
        if not self.reset_token_created:
            return False
        from datetime import timedelta
        expiry_time = self.reset_token_created + timedelta(hours=1)
        return timezone.now() < expiry_time
    
    def get_avatar_url(self):
        """Return avatar URL or default avatar"""
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return None  # Return None to trigger initials in template
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
        from datetime import date, timedelta
        
        today = date.today()
        
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
