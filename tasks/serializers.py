from rest_framework import serializers
from .models import Task, Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'color']


class TaskSerializer(serializers.ModelSerializer):
    categories = CategorySerializer(many=True, read_only=True)
    category_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        queryset=Category.objects.all(),
        source='categories'
    )
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id',
            'title',
            'description',
            'complete',
            'priority',
            'priority_display',
            'due_date',
            'created',
            'categories',
            'category_ids',
            'is_overdue',
        ]
        read_only_fields = ['id', 'created', 'is_overdue']
    
    def create(self, validated_data):
        # Extract categories from validated data
        categories = validated_data.pop('categories', [])
        
        # Create task with user from context
        task = Task.objects.create(
            user=self.context['request'].user,
            **validated_data
        )
        
        # Add categories
        if categories:
            task.categories.set(categories)
        
        return task