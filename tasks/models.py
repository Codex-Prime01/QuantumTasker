from turtle import color, mode
from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#00f5ff')
    
    class Meta:
        verbose_name_plural = 'Categories' #correct plural in admin
        
    def __str__(self):
        return self.name
    

class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    complete = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    categories = models.ManyToManyField(Category, blank=True)
        
     
    def __str__(self):
        return self.title
        return self.title
    
    
    