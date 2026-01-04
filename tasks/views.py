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
from django.views.decorators.http import require_POST, require_http_methods
import json
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.hashers import check_password, make_password
from .forms import UserUpdateForm, ProfileUpdateForm,PasswordChangeForm
from .forms import (
    NotificationSettingsForm, 
    AppearanceSettingsForm, 
    TaskDefaultsForm, 
    PrivacySettingsForm
)
import os
from .models import TaskTemplate, TemplateItem
import uuid  # Add this at the top
from django.utils import timezone  # Add this too
from django.conf import settings
from django.core.files.base import ContentFile
import base64




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


# ========================================
# REGISTRATION - Keep only ONE version
# ========================================
def registerUser(request):
    """User registration - auto-login after signup"""
    if request.method == 'POST':
        form = CustomUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Get or create profile
            from .models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # Auto-verify user (skip email verification for now)
            profile.email_verified = True
            profile.save()
            
            # Login user automatically
            login(request, user)
            
            messages.success(
                request, 
                f'🎉 Welcome to Quantum Manager, {user.username}! Your account is ready.'
            )
            
            # Redirect to home page
            return redirect('/')
           
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'❌ {error}')
    else:
        form = CustomUserForm()
    
    context = {'form': form}
    return render(request, 'tasks/register.html', context)


# ========================================
# EMAIL VERIFICATION FUNCTIONS
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
def create_task(request):
    """Dedicated page for creating new tasks"""
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            
             # Handle custom ringtone upload
            custom_tone_data = request.POST.get('custom_tone_data')
            if custom_tone_data:
                try:
                    tone_info = json.loads(custom_tone_data)
                    
                    # Extract base64 data
                    data_url = tone_info['data']
                    format, datastr = data_url.split(';base64,')
                    
                    # Create filename
                    ext = tone_info['name'].split('.')[-1]
                    filename = f"custom_tone_{request.user.id}_{task.id}.{ext}"
                    
                    # Save file
                    file_data = ContentFile(base64.b64decode(datastr), name=filename)
                    
                    # Create media directory if it doesn't exist
                    upload_path = os.path.join(settings.MEDIA_ROOT, 'alarm_tones', str(request.user.id))
                    os.makedirs(upload_path, exist_ok=True)
                    
                    # Save file path
                    file_path = os.path.join('alarm_tones', str(request.user.id), filename)
                    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
                    
                    with open(full_path, 'wb') as f:
                        f.write(file_data.read())
                    
                    # Store relative URL in task
                    task.alarm_tone = f'/media/{file_path}'
                    
                except Exception as e:
                    print(f"Error saving custom tone: {e}")
                    # Fall back to classic tone
                    task.alarm_tone = 'classic'
            
            
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


# REPLACE your send_verification_email function with this:
def send_verification_email(request, user):
    """Send verification email to user - FIXED VERSION"""
    profile = user.profile
    
    # Build proper URL for production/development
    if settings.DEBUG:
        domain = request.get_host()
        protocol = 'http'
    else:
        domain = os.environ.get('RENDER_EXTERNAL_HOSTNAME', request.get_host())
        protocol = 'https'
    
    verification_url = f"{protocol}://{domain}/verify-email/{profile.verification_token}/"
    
    # Email subject
    subject = 'Verify Your Email - Quantum Manager'
    
    # Try to load HTML template, fallback to plain text
    try:
        html_message = render_to_string('tasks/emails/verification_email.html', {
            'user': user,
            'verification_url': verification_url,
        })
        plain_message = strip_tags(html_message)
    except Exception as e:
        # If template doesn't exist, use plain text
        print(f"Template error: {e}")
        plain_message = f"""
Hi {user.username}!

Welcome to Quantum Manager! Please verify your email by clicking the link below:

{verification_url}

This link will expire in 24 hours.

If you didn't create this account, please ignore this email.

Thanks,
The Quantum Manager Team
        """
        html_message = None
    
    # Send email - ONLY ONE CALL
    try:
        if html_message:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message,
                fail_silently=False,
            )
        else:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        print(f"✅ Verification email sent to {user.email}")
        return True
        
    except Exception as e:
        print(f"❌ Email failed: {str(e)}")
        raise



def verification_sent(request):
    """Page shown after registration"""
    return render(request, 'tasks/verification_sent.html')

def verify_email(request, token):
    """Verify user's email with token"""
    from .models import UserProfile
    
    try:
        profile = UserProfile.objects.get(verification_token=token)
        
        # Check if token is expired (optional)
        # if not profile.is_verification_token_valid():
        #     messages.error(request, '⏰ Verification link expired.')
        #     return redirect('resend_verification')
        
        # Mark as verified
        profile.email_verified = True
        profile.save()
        
        # Login the user
        login(request, profile.user)
        
        messages.success(
            request, 
            f'✅ Email verified! Welcome to Quantum Manager, {profile.user.username}!'
        )
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
        profile.verification_token = uuid.uuid4()
        profile.verification_token_created = timezone.now()
        profile.save()
        
        # Try to send email
        try:
            send_verification_email(request, request.user)
            messages.success(request, '📧 Verification email sent! Check your inbox.')
        except Exception as e:
            messages.error(request, f'❌ Failed to send email: {str(e)}')
        
        return redirect('verification_sent')
    
    return render(request, 'tasks/resend_verification.html')


# ========================================
# PASSWORD RESET FUNCTIONS
# ========================================
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
            
            # Try to send email
            try:
                send_password_reset_email(request, user)
                messages.success(
                    request, 
                    f'📧 Password reset link sent to {email}! Check your inbox.'
                )
            except Exception as e:
                # Email failed - show error
                print(f"Email error: {str(e)}")
                messages.error(
                    request,
                    f'⚠️ Email service error. Please try again later or contact support.'
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

# REPLACE your send_password_reset_email function with this:

def send_password_reset_email(request, user):
    """Send password reset email to user - FIXED VERSION"""
    profile = user.profile
    
    # Build proper URL
    if settings.DEBUG:
        domain = request.get_host()
        protocol = 'http'
    else:
        domain = os.environ.get('RENDER_EXTERNAL_HOSTNAME', request.get_host())
        protocol = 'https'
    
    reset_url = f"{protocol}://{domain}/reset-password/{profile.reset_token}/"
    
    # Email subject
    subject = 'Reset Your Password - Quantum Manager'
    
    # Try to load HTML template, fallback to plain text
    try:
        html_message = render_to_string('tasks/emails/password_reset_email.html', {
            'user': user,
            'reset_url': reset_url,
        })
        plain_message = strip_tags(html_message)
    except Exception as e:
        print(f"Template error: {e}")
        plain_message = f"""
Hi {user.username},

You requested to reset your password for Quantum Manager.

Click the link below to reset your password:

{reset_url}

This link will expire in 1 hour.

If you didn't request this, please ignore this email.

Thanks,
The Quantum Manager Team
        """
        html_message = None
    
    # Send email - ONLY ONE CALL
    try:
        if html_message:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message,
                fail_silently=False,
            )
        else:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        print(f"✅ Password reset email sent to {user.email}")
        return True
        
    except Exception as e:
        print(f"❌ Email failed: {str(e)}")
        raise


def reset_link_sent(request):
    """Page shown after requesting password reset"""
    return render(request, 'tasks/reset_link_sent.html')


def reset_password(request, token):
    """Reset password with token"""
    from .models import UserProfile
    
    try:
        profile = UserProfile.objects.get(reset_token=token)
        
        # Check if token is expired (optional, if you have this method)
        # if hasattr(profile, 'is_reset_token_valid') and not profile.is_reset_token_valid():
        #     messages.error(request, '⏰ Reset link expired. Please request a new one.')
        #     return redirect('forgot_password')
        
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
def userp_settings(request):
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
                return redirect('userp_settings')
            else:
                messages.error(request, '❌ Please correct the errors below.')
        
        # Appearance Settings
        elif form_type == 'appearance':
            form = AppearanceSettingsForm(request.POST, instance=profile_obj)
            if form.is_valid():
                form.save()
                messages.success(request, '✅ Appearance settings updated!')
                return redirect('userp_settings')
            else:
                messages.error(request, '❌ Please correct the errors below.')
        
        # Task Defaults
        elif form_type == 'task_defaults':
            form = TaskDefaultsForm(request.POST, instance=profile_obj)
            if form.is_valid():
                form.save()
                messages.success(request, '✅ Task defaults updated!')
                return redirect('userp_settings')
            else:
                messages.error(request, '❌ Please correct the errors below.')
        
        # Privacy Settings
        elif form_type == 'privacy':
            form = PrivacySettingsForm(request.POST, instance=profile_obj)
            if form.is_valid():
                form.save()
                messages.success(request, '✅ Privacy settings updated!')
                return redirect('userp_settings')
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

def trial(request):
    return render(request=request, template_name='tasks/trial.html')
    
def offline_page(request):
    """Offline page for PWA"""
    return render(request, 'tasks/offline.html')

@login_required
def notes_list(request):
    """View all notes"""
    notes = Note.objects.filter(user=request.user, is_archived=False)
    
    # Filter by category
    category = request.GET.get('category')
    if category:
        notes = notes.filter(category=category)
    
    # Search
    search_query = request.GET.get('search', '').strip()
    if search_query:
        notes = notes.filter(
            Q(title__icontains=search_query) | 
            Q(content__icontains=search_query) |
            Q(tags__icontains=search_query)
        )
    
    # Stats
    total_notes = Note.objects.filter(user=request.user, is_archived=False).count()
    pinned_count = notes.filter(is_pinned=True).count()
    
    context = {
        'notes': notes,
        'total_notes': total_notes,
        'pinned_count': pinned_count,
        'search_query': search_query,
        'selected_category': category,
    }
    
    return render(request, 'tasks/notes_list.html', context)


@login_required
def create_note(request):
    """Create a new note"""
    if request.method == 'POST':
        form = NoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            messages.success(request, f'✅ Note "{note.title}" created!')
            return redirect('notes_list')
        else:
            messages.error(request, '❌ Failed to create note.')
    else:
        form = NoteForm()
    
    return render(request, 'tasks/create_note.html', {'form': form})


@login_required
def update_note(request, pk):
    """Update a note"""
    note = Note.objects.get(id=pk, user=request.user)
    
    if request.method == 'POST':
        form = NoteForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Note "{note.title}" updated!')
            return redirect('notes_list')
    else:
        form = NoteForm(instance=note)
    
    return render(request, 'tasks/update_note.html', {'form': form, 'note': note})


@login_required
def delete_note(request, pk):
    """Delete a note"""
    note = Note.objects.get(id=pk, user=request.user)
    
    if request.method == 'POST':
        note_title = note.title
        note.delete()
        messages.success(request, f'🗑️ Note "{note_title}" deleted!')
        return redirect('notes_list')
    
    return render(request, 'tasks/delete_note.html', {'note': note})


@login_required
@require_POST
def toggle_pin_note(request, pk):
    """Toggle pin status (AJAX)"""
    note = Note.objects.get(id=pk, user=request.user)
    note.is_pinned = not note.is_pinned
    note.save()
    
    return JsonResponse({
        'success': True,
        'is_pinned': note.is_pinned
    })
    
@login_required
def archive_note(request, pk):
    """Archive a note"""
    note = Note.objects.get(id=pk, user=request.user)
    note.is_archived = True
    note.save()
    messages.success(request, f'📦 Note "{note.title}" archived!')
    return redirect('notes_list')


@login_required
def unarchive_note(request, pk):
    """Unarchive a note"""
    note = Note.objects.get(id=pk, user=request.user)
    note.is_archived = False
    note.save()
    messages.success(request, f'📂 Note "{note.title}" restored!')
    return redirect('archived_notes')


@login_required
def archived_notes(request):
    """View archived notes"""
    notes = Note.objects.filter(user=request.user, is_archived=True)
    
    # Search
    search_query = request.GET.get('search', '').strip()
    if search_query:
        notes = notes.filter(
            Q(title__icontains=search_query) | 
            Q(content__icontains=search_query)
        )
    
    context = {
        'notes': notes,
        'total_notes': notes.count(),
        'search_query': search_query,
    }
    
    return render(request, 'tasks/archived_notes.html', context)

@login_required
def convert_note_to_task(request, pk):
    """Convert a note into a task"""
    note = Note.objects.get(id=pk, user=request.user)
    
    # Create task from note
    task = Task.objects.create(
        user=request.user,
        title=note.title,
        description=note.content,
        priority='medium',  # Default priority
    )
    
    # Optional: Archive the note after converting
    note.is_archived = True
    note.save()
    
    messages.success(request, f'✅ Note "{note.title}" converted to task!')
    return redirect('/')


from django.http import HttpResponse

@login_required
def export_note_as_text(request, pk):
    """Export a note as a text file"""
    note = Note.objects.get(id=pk, user=request.user)
    
    # Create text content
    content = f"""
========================================
{note.title}
========================================

Category: {note.get_category_display()}
Created: {note.created.strftime('%B %d, %Y at %I:%M %p')}
Tags: {note.tags if note.tags else 'None'}

----------------------------------------
CONTENT:
----------------------------------------

{note.content}

========================================
Exported from Quantum Manager
========================================
    """
    
    # Create HTTP response with text file
    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{note.title}.txt"'
    
    return response


@login_required
def export_all_notes(request):
    """Export all notes as one text file"""
    notes = Note.objects.filter(user=request.user, is_archived=False)
    
    content = f"""
========================================
MY NOTES - QUANTUM MANAGER
========================================
Total Notes: {notes.count()}
Exported: {timezone.now().strftime('%B %d, %Y at %I:%M %p')}
========================================

"""
    
    for i, note in enumerate(notes, 1):
        content += f"""
{'='*40}
NOTE #{i}: {note.title}
{'='*40}
Category: {note.get_category_display()}
Created: {note.created.strftime('%B %d, %Y')}
Tags: {note.tags if note.tags else 'None'}

{note.content}
 
"""
    
    content += """
========================================
END OF EXPORT
========================================
"""
    
    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="all_notes_{timezone.now().strftime("%Y%m%d")}.txt"'
    
    return response



@login_required
@require_http_methods(["GET"])
def check_due_tasks(request):
    """API endpoint to check for due tasks with alarms"""
    from django.utils import timezone
    
    now = timezone.now()
    
    # Get tasks that are due and have alarms enabled
    # Check tasks whose alarm time is within the last 5 minutes
    due_tasks = Task.objects.filter(
        user=request.user,
        complete=False,
        alarm_enabled=True,
        alarm_time__lte=now,
        alarm_time__gte=now - timedelta(minutes=5)
    ).exclude(
        alarm_snoozed_until__gt=now  # Not snoozed
    )
    
    tasks_data = []
    for task in due_tasks:
        tasks_data.append({
            'id': task.id,
            'title': task.title,
            'description': task.description or '',
            'priority': task.priority,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'alarm_time': task.alarm_time.isoformat() if task.alarm_time else None,
            'alarm_tone': task.alarm_tone or 'classic',
        })
    
    return JsonResponse({
        'success': True,
        'due_tasks': tasks_data,
        'count': len(tasks_data)
    })


@login_required
@require_http_methods(["POST"])
def snooze_alarm(request, pk):
    """Snooze an alarm for X minutes"""
    from django.utils import timezone
    
    try:
        data = json.loads(request.body)
        minutes = int(data.get('minutes', 10))
        
        task = Task.objects.get(id=pk, user=request.user)
        task.alarm_snoozed_until = timezone.now() + timedelta(minutes=minutes)
        task.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Alarm snoozed for {minutes} minutes',
            'snoozed_until': task.alarm_snoozed_until.isoformat()
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