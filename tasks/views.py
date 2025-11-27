import re
from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import *
from .forms import *
from django.contrib.auth import login, authenticate, logout
from django.db.models import Count, Q
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages


# Create your views here.           
@login_required                   
def index(request):
    from django.db.models import Count, Q, Case, When, IntegerField
    
    allTasks = Task.objects.filter(user=request.user)
    tasks = allTasks
    totalTask = allTasks.count()
    pending_count = allTasks.filter(complete=False).count()
    #get all categories with task counts
    categories = Category.objects.annotate(
        task_count = Count('task', filter=models.Q(task__user=request.user))
    )
    
    search_query = request.GET.get('search', '').strip()
    
    if search_query:
        # Search in title OR description (case-insensitive)
        tasks = tasks.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    
    #checks filtering by category
    category_id = request.GET.get('category')
    selected_category = None
    
    if category_id:
        try:
            selected_category = Category.objects.get(id=category_id)
            tasks = tasks.filter(categories=selected_category)
        except:
            pass 
        
    sort_by = request.GET.get('sort', 'created')  # Default: sort by created date
    order = request.GET.get('order', 'desc')  # Default: descending (newest first)
    
    # Define priority order for sorting
    priority_order = Case(
        When(priority='urgent', then=1),
        When(priority='high', then=2),
        When(priority='medium', then=3),
        When(priority='low', then=4),
        output_field=IntegerField(),
    )
    
    # Apply sorting
    if sort_by == 'due_date':
        # Sort by due date (tasks without due date go to end)
        if order == 'asc':
            tasks = tasks.order_by('due_date', 'created')
        else:
            tasks = tasks.order_by('-due_date', '-created')
    
    elif sort_by == 'priority':
        # Sort by priority (urgent first)
        if order == 'asc':
            tasks = tasks.order_by(priority_order, 'created')
        else:
            tasks = tasks.order_by(priority_order, 'created')  # Urgent always first
    
    elif sort_by == 'title':
        # Sort alphabetically
        if order == 'asc':
            tasks = tasks.order_by('title')
        else:
            tasks = tasks.order_by('-title')
    
    else:  # Default: sort by created date
        if order == 'asc':
            tasks = tasks.order_by('created')  # Oldest first
        else:
            tasks = tasks.order_by('-created')  # Newest first
    
    
    #handle task creation
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False) #this doesnt save it yet, jus creates an instance
            task.user = request.user
            form.save()
            form.save_m2m() #this saves the categories
            messages.success(request, f'✅ Task "{task.title}" created successfully!')
            return redirect('/')
        else:
            messages.error(request, '❌ Failed to create task. Please check the form.')  
  
    
    else:
        form = TaskForm() 
    
    context = {'tasks': tasks, 'form': form, 'categories' : categories, 'selected_category': selected_category, 'totalTasks' : totalTask, 'pending_count': pending_count,'sort_by': sort_by, 'order': order, 'search_query' : search_query} 
    
    
    return render(request, 'tasks/index.html', context)
 
@login_required
def updateTask(request, pk):
     
     task = Task.objects.get(id=pk)
     
     if task.user != request.user:
         messages.error(request, '❌ You cannot edit tasks that don\'t belong to you!')  
       
         return redirect('/')
     
     form = TaskForm(instance=task)
     
     if request.method == 'POST':
         form = TaskForm(request.POST,  instance=task)
         if form.is_valid():
             form.save()
             messages.success(request, f'✅ Task "{task.title}" updated successfully!')
             return redirect('/')
         
         else:
            messages.error(request, '❌ Failed to update task. Please check the form.')
     context = {'form' : form, 'task' : task}
     
     return render(request, 'tasks/update.html', context) 
 
@login_required
def deleteTask(request, pk):
    item = Task.objects.get(id=pk)
    
    if item.user != request.user:
        messages.error(request, '❌ You cannot delete tasks that don\'t belong to you!')
        return redirect('/')
    
    if request.method == 'POST':
        task_title = item.title
        item.delete()
        messages.success(request, f'🗑️ Task "{task_title}" deleted successfully!')
        return redirect('/')
    
    context = {'item' : item}
    return render(request, 'tasks/delete.html', context)

# user registration view
def registerUser(request):
    if request.method == 'POST':
        form = CustomUserForm(request.POST) #use our custom user form
        if form.is_valid():
            user = form.save()
            login(request, user) #log the user in after registration
            return redirect('/')
        else:
            messages.error(request, '❌ Registration failed. Please check the form.')
    else:
        form = CustomUserForm()#empty form for GET request
    context = {'form': form} #context to pass to template
    
    return render(request, 'tasks/register.html', context) #render the registration template


# user login view
def loginUser(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST) #use django's built-in authentication form
        
        if form.is_valid():
            username = form.cleaned_data.get('username') #get username from the form
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password) #authenticate the user
            if user is not None:
                login(request, user)
                messages.success(request, f'✅ Welcome back, {username}!')
                return redirect('/')
            
            else:
                messages.error(request, '❌ Invalid username or password.')
    else:
        form = AuthenticationForm()#empty form for GET request
    context = {'form': form} #context to pass to template
    return render(request, 'tasks/login.html', context) #render the login template


def logoutUser(request):
    logout(request)
    return redirect('/login/')


@login_required
def dashboard(request):
    from django.db.models import Count, Q, Case, When, IntegerField
    from django.utils import timezone
    from datetime import timedelta
    
    # Get all user's tasks
    user_tasks = Task.objects.filter(user=request.user)
    
    # Overall Statistics
    total_tasks = user_tasks.count()
    completed_tasks = user_tasks.filter(complete=True).count()
    pending_tasks = user_tasks.filter(complete=False).count()
    
    # Calculate completion rate
    if total_tasks > 0:
        completion_rate = round((completed_tasks / total_tasks) * 100, 1)
    else:
        completion_rate = 0
    
    # Priority Breakdown
    priority_stats = {
        'urgent': user_tasks.filter(priority='urgent').count(),
        'high': user_tasks.filter(priority='high').count(),
        'medium': user_tasks.filter(priority='medium').count(),
        'low': user_tasks.filter(priority='low').count(),
    }
    
    # Category Distribution
    category_stats = []
    categories = Category.objects.annotate(
        task_count=Count('task', filter=Q(task__user=request.user))
    ).filter(task_count__gt=0)  # Only categories with tasks
    
    for category in categories:
        category_stats.append({
            'name': category.name,
            'count': category.task_count,
            'color': category.color,
        })
    
    # Overdue Tasks
    overdue_count = user_tasks.filter(
        Q(due_date__lt=timezone.now()) & Q(complete=False)
    ).count()
    
    # Upcoming Deadlines (Next 7 days)
    today = timezone.now()
    next_week = today + timedelta(days=7)
    upcoming_tasks = user_tasks.filter(
        Q(due_date__gte=today) & 
        Q(due_date__lte=next_week) & 
        Q(complete=False)
    ).order_by('due_date')[:5]  # Top 5 upcoming
    
    # Recent Activity (Last 5 completed tasks)
    recent_completed = user_tasks.filter(complete=True).order_by('-created')[:5]
    
    # Tasks created this week
    week_ago = today - timedelta(days=7)
    tasks_this_week = user_tasks.filter(created__gte=week_ago).count()
    
    # Tasks completed this week
    completed_this_week = user_tasks.filter(
        complete=True,
        created__gte=week_ago
    ).count()
    
    context = {
        # Overall Stats
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'completion_rate': completion_rate,
        
        # Priority & Category
        'priority_stats': priority_stats,
        'category_stats': category_stats,
        
        # Deadlines
        'overdue_count': overdue_count,
        'upcoming_tasks': upcoming_tasks,
        
        # Recent Activity
        'recent_completed': recent_completed,
        'tasks_this_week': tasks_this_week,
        'completed_this_week': completed_this_week,
    }
    
    return render(request, 'tasks/dashboard.html', context)
@login_required
def profile(request):
    """User profile page (placeholder for now)"""
    context = {
        'user': request.user,
    }
    return render(request, 'tasks/profile.html', context)


@login_required
def settings(request):
    """Settings page (placeholder for now)"""
    context = {}
    return render(request, 'tasks/settings.html', context)