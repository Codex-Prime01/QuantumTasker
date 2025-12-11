from django.core.management.base import BaseCommand
from tasks.models import Category


class Command(BaseCommand):
    help = 'Create default categories'

    def handle(self, *args, **kwargs):
        # Default categories
        categories = [
            {'name': 'Work', 'color': '#0088cc'},
            {'name': 'Personal', 'color': '#4CAF50'},
            {'name': 'Shopping', 'color': '#FF9800'},
            {'name': 'Health', 'color': '#F44336'},
            {'name': 'Study', 'color': '#9C27B0'},
            {'name': 'Finance', 'color': '#4CAF50'},
            {'name': 'Home', 'color': '#795548'},
            {'name': 'Urgent', 'color': '#E91E63'},
        ]
        
        created_count = 0
        updated_count = 0
        
        for category_data in categories:
            category, created = Category.objects.get_or_create(
                name=category_data['name'],
                defaults={'color': category_data['color']}
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created category: {category.name}')
                )
            else:
                # Update color if category already exists
                category.color = category_data['color']
                category.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'ℹ️  Updated category: {category.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Summary: {created_count} created, {updated_count} updated!'
            )
        )