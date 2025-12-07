from django.core.management.base import BaseCommand
from tasks.models import TaskTemplate, TemplateItem, Category


class Command(BaseCommand):
    help = 'Create default task templates'

    def handle(self, *args, **kwargs):
        # Get or create categories
        work_cat, _ = Category.objects.get_or_create(name='Work', defaults={'color': '#0088cc'})
        personal_cat, _ = Category.objects.get_or_create(name='Personal', defaults={'color': '#4CAF50'})
        shopping_cat, _ = Category.objects.get_or_create(name='Shopping', defaults={'color': '#FF9800'})
        health_cat, _ = Category.objects.get_or_create(name='Health', defaults={'color': '#F44336'})
        
        # Delete existing default templates to avoid duplicates
        TaskTemplate.objects.filter(is_default=True).delete()
        
        # ========================================
        # MORNING ROUTINE TEMPLATE 🌅
        # ========================================
        morning = TaskTemplate.objects.create(
            name='Morning Routine',
            description='Start your day right with this energizing morning routine',
            icon='🌅',
            is_default=True
        )
        
        morning_tasks = [
            {'title': 'Make bed', 'priority': 'low', 'order': 1},
            {'title': 'Brush teeth & wash face', 'priority': 'medium', 'order': 2},
            {'title': 'Take vitamins/medication', 'priority': 'high', 'order': 3},
            {'title': '10-minute exercise or stretch', 'priority': 'medium', 'order': 4},
            {'title': 'Healthy breakfast', 'priority': 'medium', 'order': 5},
            {'title': 'Review daily goals', 'priority': 'medium', 'order': 6},
        ]
        
        for task_data in morning_tasks:
            item = TemplateItem.objects.create(
                template=morning,
                title=task_data['title'],
                priority=task_data['priority'],
                order=task_data['order']
            )
            item.categories.add(personal_cat)
        
        # ========================================
        # WEEKLY GROCERY SHOPPING 🛒
        # ========================================
        shopping = TaskTemplate.objects.create(
            name='Weekly Grocery Shopping',
            description='Never forget essential items again',
            icon='🛒',
            is_default=True
        )
        
        shopping_tasks = [
            {'title': 'Fresh fruits & vegetables', 'priority': 'high', 'order': 1},
            {'title': 'Milk, eggs, bread', 'priority': 'high', 'order': 2},
            {'title': 'Meat & protein', 'priority': 'medium', 'order': 3},
            {'title': 'Snacks & beverages', 'priority': 'low', 'order': 4},
            {'title': 'Household supplies (toilet paper, etc.)', 'priority': 'medium', 'order': 5},
            {'title': 'Cleaning products', 'priority': 'low', 'order': 6},
        ]
        
        for task_data in shopping_tasks:
            item = TemplateItem.objects.create(
                template=shopping,
                title=task_data['title'],
                priority=task_data['priority'],
                order=task_data['order']
            )
            item.categories.add(shopping_cat)
        
        # ========================================
        # WORK DAY PREP 💼
        # ========================================
        work_prep = TaskTemplate.objects.create(
            name='Work Day Prep',
            description='Get ready for a productive workday',
            icon='💼',
            is_default=True
        )
        
        work_tasks = [
            {'title': 'Check emails & messages', 'priority': 'high', 'order': 1},
            {'title': 'Review today\'s calendar', 'priority': 'high', 'order': 2},
            {'title': 'Prioritize top 3 tasks', 'priority': 'urgent', 'order': 3},
            {'title': 'Prepare for meetings', 'priority': 'high', 'order': 4},
            {'title': 'Update project status', 'priority': 'medium', 'order': 5},
            {'title': 'Clear workspace/desk', 'priority': 'low', 'order': 6},
        ]
        
        for task_data in work_tasks:
            item = TemplateItem.objects.create(
                template=work_prep,
                title=task_data['title'],
                priority=task_data['priority'],
                order=task_data['order']
            )
            item.categories.add(work_cat)
        
        # ========================================
        # HOUSE CLEANING 🧹
        # ========================================
        cleaning = TaskTemplate.objects.create(
            name='Weekly House Cleaning',
            description='Keep your space tidy and organized',
            icon='🧹',
            is_default=True
        )
        
        cleaning_tasks = [
            {'title': 'Vacuum all rooms', 'priority': 'medium', 'order': 1},
            {'title': 'Mop kitchen & bathroom floors', 'priority': 'medium', 'order': 2},
            {'title': 'Clean bathroom (toilet, sink, shower)', 'priority': 'high', 'order': 3},
            {'title': 'Dust furniture & surfaces', 'priority': 'low', 'order': 4},
            {'title': 'Do laundry', 'priority': 'medium', 'order': 5},
            {'title': 'Take out trash & recycling', 'priority': 'medium', 'order': 6},
            {'title': 'Change bed sheets', 'priority': 'low', 'order': 7},
        ]
        
        for task_data in cleaning_tasks:
            item = TemplateItem.objects.create(
                template=cleaning,
                title=task_data['title'],
                priority=task_data['priority'],
                order=task_data['order']
            )
            item.categories.add(personal_cat)
        
        # ========================================
        # EVENING WIND DOWN 🌙
        # ========================================
        evening = TaskTemplate.objects.create(
            name='Evening Wind Down',
            description='Relax and prepare for a restful night',
            icon='🌙',
            is_default=True
        )
        
        evening_tasks = [
            {'title': 'Prepare tomorrow\'s outfit', 'priority': 'low', 'order': 1},
            {'title': 'Pack bag/lunch for tomorrow', 'priority': 'medium', 'order': 2},
            {'title': 'Review tomorrow\'s schedule', 'priority': 'medium', 'order': 3},
            {'title': 'Brush teeth & skincare routine', 'priority': 'medium', 'order': 4},
            {'title': 'Read or journal for 15 minutes', 'priority': 'low', 'order': 5},
            {'title': 'Set alarm for morning', 'priority': 'high', 'order': 6},
        ]
        
        for task_data in evening_tasks:
            item = TemplateItem.objects.create(
                template=evening,
                title=task_data['title'],
                priority=task_data['priority'],
                order=task_data['order']
            )
            item.categories.add(personal_cat)
        
        # ========================================
        # HEALTH CHECK 💊
        # ========================================
        health = TaskTemplate.objects.create(
            name='Daily Health Routine',
            description='Essential daily health tasks',
            icon='💊',
            is_default=True
        )
        
        health_tasks = [
            {'title': 'Take morning medication', 'priority': 'urgent', 'order': 1},
            {'title': 'Drink 8 glasses of water', 'priority': 'high', 'order': 2},
            {'title': '30 minutes of exercise', 'priority': 'high', 'order': 3},
            {'title': 'Eat 3 balanced meals', 'priority': 'high', 'order': 4},
            {'title': 'Take evening medication', 'priority': 'urgent', 'order': 5},
            {'title': 'Get 7-8 hours of sleep', 'priority': 'high', 'order': 6},
        ]
        
        for task_data in health_tasks:
            item = TemplateItem.objects.create(
                template=health,
                title=task_data['title'],
                priority=task_data['priority'],
                order=task_data['order'],
                is_recurring=True,
                recurring_frequency='daily'
            )
            item.categories.add(health_cat)
        
        self.stdout.write(self.style.SUCCESS('✅ Successfully created 6 default templates!'))
        self.stdout.write(self.style.SUCCESS('   🌅 Morning Routine'))
        self.stdout.write(self.style.SUCCESS('   🛒 Weekly Grocery Shopping'))
        self.stdout.write(self.style.SUCCESS('   💼 Work Day Prep'))
        self.stdout.write(self.style.SUCCESS('   🧹 Weekly House Cleaning'))
        self.stdout.write(self.style.SUCCESS('   🌙 Evening Wind Down'))
        self.stdout.write(self.style.SUCCESS('   💊 Daily Health Routine'))