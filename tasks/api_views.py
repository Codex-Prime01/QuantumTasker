from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from .models import Task, Category
from .serializers import TaskSerializer, CategorySerializer


class TaskViewSet(viewsets.ModelViewSet):
    """
    API endpoint for tasks.
    
    Provides:
    - GET /api/tasks/ - List all tasks
    - POST /api/tasks/ - Create a task
    - GET /api/tasks/{id}/ - Get specific task
    - PUT /api/tasks/{id}/ - Update task
    - DELETE /api/tasks/{id}/ - Delete task
    """
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['created', 'due_date', 'priority', 'title']
    ordering = ['-created']  # Default ordering
    
    def get_queryset(self):
        """Only return tasks belonging to the logged-in user"""
        queryset = Task.objects.filter(user=self.request.user)
        
        # Filter by category
        category_id = self.request.query_params.get('category', None)
        if category_id:
            queryset = queryset.filter(categories__id=category_id)
        
        # Filter by priority
        priority = self.request.query_params.get('priority', None)
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Filter by completion status
        complete = self.request.query_params.get('complete', None)
        if complete is not None:
            queryset = queryset.filter(complete=complete.lower() == 'true')
        
        return queryset
    
    def perform_create(self, serializer):
        """Automatically assign the logged-in user when creating a task"""
        serializer.save(user=self.request.user)
    
    def perform_update(self, serializer):
        """Ensure user can only update their own tasks"""
        if serializer.instance.user != self.request.user:
            raise PermissionError("You can only update your own tasks!")
        serializer.save()
    
    def perform_destroy(self, instance):
        """Ensure user can only delete their own tasks"""
        if instance.user != self.request.user:
            raise PermissionError("You can only delete your own tasks!")
        instance.delete()
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Custom endpoint: GET /api/tasks/overdue/"""
        from django.utils import timezone
        overdue_tasks = self.get_queryset().filter(
            Q(due_date__lt=timezone.now()) & Q(complete=False)
        )
        serializer = self.get_serializer(overdue_tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Custom endpoint: GET /api/tasks/upcoming/"""
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now()
        next_week = today + timedelta(days=7)
        
        upcoming_tasks = self.get_queryset().filter(
            Q(due_date__gte=today) & 
            Q(due_date__lte=next_week) & 
            Q(complete=False)
        ).order_by('due_date')
        
        serializer = self.get_serializer(upcoming_tasks, many=True)
        return Response(serializer.data)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for categories.
    
    Provides:
    - GET /api/categories/ - List all categories
    - POST /api/categories/ - Create a category
    - GET /api/categories/{id}/ - Get specific category
    - PUT /api/categories/{id}/ - Update category
    - DELETE /api/categories/{id}/ - Delete category
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]