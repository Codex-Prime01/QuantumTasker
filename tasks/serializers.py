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
        source='categories',
        required=False,
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
        # The view passes user=... through serializer.save(), so it is
        # already inside validated_data. (Passing it twice used to crash.)
        categories = validated_data.pop('categories', [])
        task = Task.objects.create(**validated_data)
        if categories:
            task.categories.set(categories)
        return task
