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
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.hashers import check_password, make_password
from .forms import UserUpdateForm, ProfileUpdateForm, PasswordChangeForm
from .forms import (
    NotificationSettingsForm, 
    AppearanceSettingsForm, 
    TaskDefaultsForm, 
    PrivacySettingsForm
)

from .models import TaskTemplate, TemplateItem


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
             task = form.save(commit=False)  # 👈 SAVE TO VARIABLE
             task.save()  # 👈 SAVE THE TASK FIRST!
             form.save_m2m()  # 👈 THEN SAVE CATEGORIES!
             messages.success(request, f'✅ Task "{task.title}" updated successfully!')
             return redirect('/')
         
         else:
            for field, errors in form.errors.items():
                 for error in errors:
                     messages.error(request, f'❌ {field}: {error}')
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
            
             # Get or create profile (should be created by signal, but just in case)
            from .models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # Send verification email
            send_verification_email(request, user)
            
            # Show message and redirect to verification page
            messages.info(
                request, 
                f'📧 Welcome {user.username}! Please check your email to verify your account.'
            )
            return redirect('verification_sent')
           
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

@login_required
def create_task(request):
    """Dedicated page for creating new tasks"""
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            form.save_m2m()
            messages.success(request, f'✅ Task "{task.title}" created successfully!')
            
            if task.is_recurring and task.recurring_frequency != 'none':
                recurring_info = task.get_recurring_info()
                messages.info(request, f'{recurring_info}')
            
            return redirect('/')
        else:
            messages.error(request, '❌ Failed to create task. Please check the form.')
    else:
        form = TaskForm()
    
    context = {'form': form}
    return render(request, 'tasks/create.html', context)

"""

@login_required
@require_POST
def quick_toggle_complete(request, pk):
    Quick toggle task completion status via AJAX
    try:
        task = Task.objects.get(id=pk, user=request.user)
        
        # Parse JSON data
        data = json.loads(request.body)
        task.complete = data.get('complete', False)
        task.save()
        
        return JsonResponse({
            'success': True,
            'complete': task.complete
        })
    except Task.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Task not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
        """

def verification_sent(request):
    """Page shown after registration"""
    return render(request, 'tasks/verification_sent.html')


def verify_email(request, token):
    """Verify user's email with token"""
    from .models import UserProfile
    
    try:
        profile = UserProfile.objects.get(verification_token=token)
        
        # Check if token is expired
        if not profile.is_verification_token_valid():
            messages.error(request, '⏰ Verification link expired. Please request a new one.')
            return redirect('resend_verification')
        
        # Mark as verified
        profile.email_verified = True
        profile.save()
        
        # Log the user in
        login(request, profile.user)
        
        messages.success(request, f'✅ Email verified! Welcome to Quantum Manager, {profile.user.username}!')
        return redirect('/')
        
    except UserProfile.DoesNotExist:
        messages.error(request, '❌ Invalid verification link.')
        return redirect('login')


@login_required
def resend_verification(request):
    """Resend verification email"""
    profile = request.user.profile
    
    if profile.email_verified:
        messages.info(request, 'Your email is already verified!')
        return redirect('/')
    
    if request.method == 'POST':
        # Generate new token
        import uuid
        profile.verification_token = uuid.uuid4()
        profile.verification_token_created = timezone.now()
        profile.save()
        
        # Send new email
        send_verification_email(request, request.user)
        
        messages.success(request, '📧 Verification email sent! Check your inbox.')
        return redirect('verification_sent')
    
    return render(request, 'tasks/resend_verification.html')



def send_verification_email(request, user):
    """Send verification email to user"""
    profile = user.profile
    
    # Build verification URL
    current_site = get_current_site(request)
    verification_url = f"http://{current_site.domain}/verify-email/{profile.verification_token}/"
    
    # Email subject
    subject = 'Verify Your Email - Quantum Manager'
    
    # Email body (HTML)
    html_message = render_to_string('tasks/emails/verification_email.html', {
        'user': user,
        'verification_url': verification_url,
    })
    
    # Plain text version
    plain_message = strip_tags(html_message)
    
    # Send email
    send_mail(
        subject,
        plain_message,
        'noreply@quantummanager.com',
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )

def forgot_password(request):
    """Request password reset - enter email"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, '❌ Please enter your email address.')
            return redirect('forgot_password')
        
        # Check if user exists with this email
        try:
            user = User.objects.get(email=email)
            profile = user.profile
            
            # Generate new reset token
            profile.reset_token = uuid.uuid4()
            profile.reset_token_created = timezone.now()
            profile.save()
            
            # Send reset email
            send_password_reset_email(request, user)
            
            messages.success(
                request, 
                f'📧 Password reset link sent to {email}! Check your inbox.'
            )
            return redirect('reset_link_sent')
            
        except User.DoesNotExist:
            # Security: Don't reveal if email exists or not!
            messages.success(
                request, 
                f'📧 If an account exists with {email}, you will receive a password reset link.'
            )
            return redirect('reset_link_sent')
    
    return render(request, 'tasks/forgot_password.html')


def send_password_reset_email(request, user):
    """Send password reset email to user"""
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from django.contrib.sites.shortcuts import get_current_site
    
    profile = user.profile
    
    # Build reset URL
    current_site = get_current_site(request)
    reset_url = f"http://{current_site.domain}/reset-password/{profile.reset_token}/"
    
    # Email subject
    subject = 'Reset Your Password - Quantum Manager'
    
    # Email body (HTML)
    html_message = render_to_string('tasks/emails/password_reset_email.html', {
        'user': user,
        'reset_url': reset_url,
    })
    
    # Plain text version
    plain_message = strip_tags(html_message)
    
    # Send email
    send_mail(
        subject,
        plain_message,
        'noreply@quantummanager.com',
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )


def reset_link_sent(request):
    """Page shown after requesting password reset"""
    return render(request, 'tasks/reset_link_sent.html')


def reset_password(request, token):
    """Reset password with token"""
    from tasks.models import UserProfile
    
    
    try:
        profile = UserProfile.objects.get(reset_token=token)
        
        # Check if token is expired
        if not profile.is_reset_token_valid():
            messages.error(request, '⏰ Reset link expired. Please request a new one.')
            return redirect('forgot_password')
        
        if request.method == 'POST':
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            
            # Validation
            if not password1 or not password2:
                messages.error(request, '❌ Please fill in all fields.')
                return redirect('reset_password', token=token)
            
            if password1 != password2:
                messages.error(request, '❌ Passwords do not match.')
                return redirect('reset_password', token=token)
            
            if len(password1) < 8:
                messages.error(request, '❌ Password must be at least 8 characters long.')
                return redirect('reset_password', token=token)
            
            # Update password
            user = profile.user
            user.password = make_password(password1)
            user.save()
            
            # Invalidate the reset token (security!)
            profile.reset_token = uuid.uuid4()
            profile.reset_token_created = None
            profile.save()
            
            messages.success(request, '✅ Password reset successful! Please login with your new password.')
            return redirect('login')
        
        context = {'token': token, 'username': profile.user.username}
        return render(request, 'tasks/reset_password.html', context)
        
    except UserProfile.DoesNotExist:
        messages.error(request, '❌ Invalid reset link.')
        return redirect('forgot_password')


@login_required
def profile(request):
    """User profile page with editing capabilities"""
    profile_obj = request.user.profile
    
    # Handle form submissions
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        # Profile Info Update
        if form_type == 'profile_info':
            user_form = UserUpdateForm(request.POST, instance=request.user)
            profile_form = ProfileUpdateForm(
                request.POST, 
                request.FILES,  # Important! For file uploads!
                instance=profile_obj
            )
            
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, '✅ Profile updated successfully!')
                return redirect('profile')
            else:
                messages.error(request, '❌ Please correct the errors below.')
        
        # Password Change
        elif form_type == 'password_change':
            password_form = PasswordChangeForm(request.POST)
            
            if password_form.is_valid():
                current_password = password_form.cleaned_data['current_password']
                new_password = password_form.cleaned_data['new_password1']
                
                # Check current password is correct
                if check_password(current_password, request.user.password):
                    # Update password
                    request.user.password = make_password(new_password)
                    request.user.save()
                    
                    # Update session to keep user logged in
                    from django.contrib.auth import update_session_auth_hash
                    update_session_auth_hash(request, request.user)
                    
                    messages.success(request, '✅ Password changed successfully!')
                    return redirect('profile')
                else:
                    messages.error(request, '❌ Current password is incorrect.')
            else:
                messages.error(request, '❌ Please correct the errors below.')
    
    # GET request - show forms
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile_obj)
        password_form = PasswordChangeForm()
    
    # Get user statistics
    from django.db.models import Count, Q
    total_tasks = Task.objects.filter(user=request.user).count()
    completed_tasks = Task.objects.filter(user=request.user, complete=True).count()
    pending_tasks = total_tasks - completed_tasks
    
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Tasks by priority
    priority_stats = Task.objects.filter(user=request.user).values('priority').annotate(
        count=Count('id')
    )
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'completion_rate': round(completion_rate, 1),
        'priority_stats': priority_stats,
    }
    
    return render(request, 'tasks/profile.html', context)

# 👇 ADD/UPDATE THIS VIEW
@login_required
def settings(request):
    """User settings page with tabs"""
    profile_obj = request.user.profile
    
    # Handle form submissions
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        # Notification Settings
        if form_type == 'notifications':
            form = NotificationSettingsForm(request.POST, instance=profile_obj)
            if form.is_valid():
                form.save()
                messages.success(request, '✅ Notification settings updated!')
                return redirect('settings')
            else:
                messages.error(request, '❌ Please correct the errors below.')
        
        # Appearance Settings
        elif form_type == 'appearance':
            form = AppearanceSettingsForm(request.POST, instance=profile_obj)
            if form.is_valid():
                form.save()
                messages.success(request, '✅ Appearance settings updated!')
                return redirect('settings')
            else:
                messages.error(request, '❌ Please correct the errors below.')
        
        # Task Defaults
        elif form_type == 'task_defaults':
            form = TaskDefaultsForm(request.POST, instance=profile_obj)
            if form.is_valid():
                form.save()
                messages.success(request, '✅ Task defaults updated!')
                return redirect('settings')
            else:
                messages.error(request, '❌ Please correct the errors below.')
        
        # Privacy Settings
        elif form_type == 'privacy':
            form = PrivacySettingsForm(request.POST, instance=profile_obj)
            if form.is_valid():
                form.save()
                messages.success(request, '✅ Privacy settings updated!')
                return redirect('settings')
            else:
                messages.error(request, '❌ Please correct the errors below.')
        
        # Account Deletion
        elif form_type == 'delete_account':
            confirm = request.POST.get('confirm_delete')
            if confirm == request.user.username:
                # Delete user account
                user = request.user
                logout(request)
                user.delete()
                messages.success(request, '✅ Your account has been deleted. Goodbye! 👋')
                return redirect('login')
            else:
                messages.error(request, '❌ Username confirmation did not match!')
    
    # GET request - show forms
    notification_form = NotificationSettingsForm(instance=profile_obj)
    appearance_form = AppearanceSettingsForm(instance=profile_obj)
    task_defaults_form = TaskDefaultsForm(instance=profile_obj)
    privacy_form = PrivacySettingsForm(instance=profile_obj)
    
    
    
    # Get active tab from query parameter
    active_tab = request.GET.get('tab', 'notifications')
    
    context = {
        'notification_form': notification_form,
        'appearance_form': appearance_form,
        'task_defaults_form': task_defaults_form,
        'privacy_form': privacy_form,
        'active_tab': active_tab,
    }
    
    
    return render(request, 'tasks/settings.html', context)

@login_required
@require_POST
def update_theme(request):
    
    try:
        data = json.loads(request.body)
        theme = data.get('theme')
        
        if theme in ['light', 'dark', 'auto']:
            profile = request.user.profile
            profile.theme = theme
            profile.save()
            return JsonResponse({'success': True, 'theme': theme})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid theme'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    
@login_required
def quick_toggle_complete(request, pk):
    """Toggle task completion status (AJAX)"""
    from django.http import JsonResponse
    from .models import UserStats
    
    task = Task.objects.get(id=pk, user=request.user)
    task.complete = not task.complete
    
    # Get or create user stats
    stats, created = UserStats.objects.get_or_create(user=request.user)
    
    new_achievements = []
    
    # If completing a task
    if task.complete:
        # Update stats
        stats.total_tasks_completed += 1
        stats.tasks_completed_today += 1
        stats.update_streak()
        stats.save()
        
        # Check for new achievements
        new_achievements = stats.check_achievements()
        
        # If recurring task, create next occurrence
        if task.is_recurring and task.recurring_frequency != 'none':
            task.completed_date = timezone.now()
            task.save()
            next_task = task.create_next_occurrence()
            
            if next_task:
                message = f'✅ Task completed! Next occurrence created for {next_task.due_date.strftime("%B %d, %Y")}'
                
                # Add achievement notifications
                if new_achievements:
                    achievement_names = ', '.join([a.icon + ' ' + a.name for a in new_achievements])
                    message += f'\n🎉 New Achievement{"s" if len(new_achievements) > 1 else ""}: {achievement_names}!'
                 
                return JsonResponse({
                    'success': True,
                    'complete': task.complete,
                    'message': message,
                    'new_achievements': [{'name': a.name, 'icon': a.icon, 'points': a.points} for a in new_achievements]
                })
    
    # If uncompleting a task
    else:
        if stats.total_tasks_completed > 0:
            stats.total_tasks_completed -= 1
        if stats.tasks_completed_today > 0:
            stats.tasks_completed_today -= 1
        stats.save()
    
    task.save()
    
    # Return response with achievement info
    response_data = {
        'success': True,
        'complete': task.complete,
    }
    
    if new_achievements:
        response_data['new_achievements'] = [
            {
                'name': a.name, 
                'icon': a.icon, 
                'points': a.points,
                'description': a.description
            } 
            for a in new_achievements
        ]
        achievement_names = ', '.join([a.icon + ' ' + a.name for a in new_achievements])
        response_data['message'] = f'🎉 Achievement Unlocked: {achievement_names}! (+{sum(a.points for a in new_achievements)} points)'
    
    return JsonResponse(response_data)
    
@login_required
def templates_list(request):
    """View all available templates"""
    # Default templates (available to everyone)
    default_templates = TaskTemplate.objects.filter(is_default=True)
    
    # User's custom templates
    user_templates = TaskTemplate.objects.filter(user=request.user, is_default=False)
    
    context = {
        'default_templates': default_templates,
        'user_templates': user_templates,
    }
    
    return render(request, 'tasks/templates_list.html', context)


@login_required
def template_detail(request, pk):
    """View template details"""
    template = TaskTemplate.objects.get(id=pk)
    
    # Check permission (default templates or user's own)
    if not template.is_default and template.user != request.user:
        messages.error(request, '❌ You do not have permission to view this template.')
        return redirect('templates_list')
    
    items = template.items.all()
    
    context = {
        'template': template,
        'items': items,
    }
    
    return render(request, 'tasks/template_detail.html', context)


@login_required
def use_template(request, pk):
    """Create tasks from a template"""
    template = TaskTemplate.objects.get(id=pk)
    
    # Check permission
    if not template.is_default and template.user != request.user:
        messages.error(request, '❌ You do not have permission to use this template.')
        return redirect('templates_list')
    
    # Create all tasks from template
    created_tasks = template.instantiate(request.user)
    
    messages.success(
        request, 
        f'✅ Created {len(created_tasks)} tasks from "{template.name}" template!'
    )
    
    return redirect('/')


@login_required
def create_template(request):
    """Create a new custom template"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        icon = request.POST.get('icon', '📋')
        
        if not name:
            messages.error(request, '❌ Template name is required.')
            return redirect('create_template')
        
        # Create template
        template = TaskTemplate.objects.create(
            user=request.user,
            name=name,
            description=description,
            icon=icon,
            is_default=False
        )
        
        messages.success(request, f'✅ Template "{name}" created! Now add tasks to it.')
        return redirect('edit_template', pk=template.id)
    
    return render(request, 'tasks/create_template.html')


@login_required
def edit_template(request, pk):
    """Edit a template and its items"""
    template = TaskTemplate.objects.get(id=pk, user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Update template info
        if action == 'update_info':
            template.name = request.POST.get('name', template.name)
            template.description = request.POST.get('description', template.description)
            template.icon = request.POST.get('icon', template.icon)
            template.save()
            messages.success(request, '✅ Template updated!')
        
        # Add new item
        elif action == 'add_item':
            title = request.POST.get('title')
            priority = request.POST.get('priority', 'medium')
            description = request.POST.get('description', '')
            
            if title:
                TemplateItem.objects.create(
                    template=template,
                    title=title,
                    description=description,
                    priority=priority,
                    order=template.items.count() + 1
                )
                messages.success(request, f'✅ Added "{title}" to template!')
            else:
                messages.error(request, '❌ Task title is required.')
        
        return redirect('edit_template', pk=pk)
    
    items = template.items.all()
    
    context = {
        'template': template,
        'items': items,
    }
    
    return render(request, 'tasks/edit_template.html', context)


@login_required
def delete_template_item(request, template_id, item_id):
    """Delete an item from a template"""
    template = TaskTemplate.objects.get(id=template_id, user=request.user)
    item = TemplateItem.objects.get(id=item_id, template=template)
    
    item_title = item.title
    item.delete()
    
    messages.success(request, f'✅ Removed "{item_title}" from template.')
    return redirect('edit_template', pk=template_id)


@login_required
def delete_template(request, pk):
    """Delete a custom template"""
    template = TaskTemplate.objects.get(id=pk, user=request.user)
    
    if request.method == 'POST':
        template_name = template.name
        template.delete()
        messages.success(request, f'✅ Template "{template_name}" deleted.')
        return redirect('templates_list')
    
    return render(request, 'tasks/delete_template.html', {'template': template})


@login_required
def create_template_from_tasks(request):
    """Create a template from selected existing tasks"""
    if request.method == 'POST':
        task_ids = request.POST.getlist('task_ids')
        template_name = request.POST.get('template_name')
        template_icon = request.POST.get('template_icon', '📋')
        
        if not task_ids or not template_name:
            messages.error(request, '❌ Please select tasks and provide a template name.')
            return redirect('/')
        
        # Create template
        template = TaskTemplate.objects.create(
            user=request.user,
            name=template_name,
            icon=template_icon,
            is_default=False
        )
        
        # Add selected tasks to template
        for order, task_id in enumerate(task_ids, 1):
            task = Task.objects.get(id=task_id, user=request.user)
            item = TemplateItem.objects.create(
                template=template,
                title=task.title,
                description=task.description,
                priority=task.priority,
                is_recurring=task.is_recurring,
                recurring_frequency=task.recurring_frequency,
                order=order
            )
            item.categories.set(task.categories.all())
        
        messages.success(request, f'✅ Created template "{template_name}" from {len(task_ids)} tasks!')
        return redirect('templates_list')
    
    # GET - show task selection
    tasks = Task.objects.filter(user=request.user, complete=False)
    return render(request, 'tasks/create_template_from_tasks.html', {'tasks': tasks})

@login_required
def achievements_view(request):
    """View all achievements and user progress"""
    from .models import Achievement, UserAchievement, UserStats
    
    # Get or create user stats
    stats, created = UserStats.objects.get_or_create(user=request.user)
    
    # Get user's unlocked achievements
    unlocked_achievements = UserAchievement.objects.filter(
        user=request.user
    ).select_related('achievement')
    
    unlocked_ids = unlocked_achievements.values_list('achievement_id', flat=True)
    
    # Get all achievements grouped by type
    all_achievements = Achievement.objects.all()
    
    # Group achievements
    achievements_by_type = {}
    for achievement in all_achievements:
        if achievement.is_hidden and achievement.id not in unlocked_ids:
            continue  # Skip hidden achievements user hasn't unlocked
        
        achievement_type = achievement.get_achievement_type_display()
        if achievement_type not in achievements_by_type:
            achievements_by_type[achievement_type] = []
        
        # Check if unlocked
        is_unlocked = achievement.id in unlocked_ids
        
        # Calculate progress
        progress = 0
        if not is_unlocked:
            if achievement.achievement_type == 'tasks_completed':
                progress = min(100, int((stats.total_tasks_completed / achievement.requirement) * 100))
            elif achievement.achievement_type == 'streak':
                progress = min(100, int((stats.current_streak / achievement.requirement) * 100))
            elif achievement.achievement_type == 'consistency':
                progress = min(100, int((stats.longest_streak / achievement.requirement) * 100))
        else:
            progress = 100
        
        achievements_by_type[achievement_type].append({
            'achievement': achievement,
            'is_unlocked': is_unlocked,
            'progress': progress,
            'unlocked_at': next((ua.unlocked_at for ua in unlocked_achievements if ua.achievement_id == achievement.id), None)
        })
    
    context = {
        'stats': stats,
        'achievements_by_type': achievements_by_type,
        'total_achievements': all_achievements.count(),
        'unlocked_count': unlocked_achievements.count(),
        'total_points': stats.total_points,
    }
    
    return render(request, 'tasks/achievements.html', context)

def offline_page(request):
    """Offline page for PWA"""
    return render(request, 'tasks/offline.html')