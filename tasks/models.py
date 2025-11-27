from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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
    
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    complete = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=10,choices=PRIORITY_CHOICES,default='medium')
    
    categories = models.ManyToManyField(Category, blank=True)
        
     
    def __str__(self):
        return self.title
        return self.title
    
    @property
    def is_overdue(self): #new helper method
        #to check if task is overdue    
        if self.due_date and not self.complete:
            return timezone.now() > self.due_date
        return False

    