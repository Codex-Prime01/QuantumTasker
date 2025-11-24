import re
from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import *
from .forms import *
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserForm
from django.contrib.auth.decorators import login_required


# Create your views here.           
@login_required                   
def index(request):
    tasks = Task.objects.filter(user=request.user)
      
    form = TaskForm()
     
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            form.save()
        return redirect('/')
    
    context = {'tasks': tasks, 'form': form} 
    return render(request, 'tasks/index.html', context)
 
@login_required
def updateTask(request, pk):
     
     task = Task.objects.get(id=pk)
     
     if task.user != request.user:
         return redirect('/')
     
     form = TaskForm(instance=task)
     
     if request.method == 'POST':
         form = TaskForm(request.POST,  instance=task)
         if form.is_valid():
             form.save()
             return redirect('/')
     
     context = {'form' : form}
     
     return render(request, 'tasks/update.html', context) 
 
@login_required
def deleteTask(request, pk):
    item = Task.objects.get(id=pk)
    
    if item.user != request.user:
        return redirect('/')
    
    if request.method == 'POST':
        item.delete()
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
                return redirect('/')
    else:
        form = AuthenticationForm()#empty form for GET request
    context = {'form': form} #context to pass to template
    return render(request, 'tasks/login.html', context) #render the login template


def logoutUser(request):
    logout(request)
    return redirect('/login/')
