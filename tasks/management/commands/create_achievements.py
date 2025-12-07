from django.core.management.base import BaseCommand
from tasks.models import Achievement


class Command(BaseCommand):
    help = 'Create default achievements'

    def handle(self, *args, **kwargs):
        # Delete existing achievements to avoid duplicates
        Achievement.objects.all().delete()
        
        achievements = [
            # ========================================
            # TASKS COMPLETED ACHIEVEMENTS
            # ========================================
            {
                'name': 'First Steps',
                'description': 'Complete your very first task',
                'icon': '🎯',
                'achievement_type': 'tasks_completed',
                'requirement': 1,
                'points': 10,
            },
            {
                'name': 'Getting Started',
                'description': 'Complete 5 tasks',
                'icon': '✅',
                'achievement_type': 'tasks_completed',
                'requirement': 5,
                'points': 20,
            },
            {
                'name': 'Task Master',
                'description': 'Complete 25 tasks',
                'icon': '⭐',
                'achievement_type': 'tasks_completed',
                'requirement': 25,
                'points': 50,
            },
            {
                'name': 'Productivity Pro',
                'description': 'Complete 50 tasks',
                'icon': '💪',
                'achievement_type': 'tasks_completed',
                'requirement': 50,
                'points': 100,
            },
            {
                'name': 'Century Club',
                'description': 'Complete 100 tasks',
                'icon': '💯',
                'achievement_type': 'tasks_completed',
                'requirement': 100,
                'points': 200,
            },
            {
                'name': 'Task Legend',
                'description': 'Complete 500 tasks',
                'icon': '👑',
                'achievement_type': 'tasks_completed',
                'requirement': 500,
                'points': 500,
                'is_hidden': True,
            },
            
            # ========================================
            # STREAK ACHIEVEMENTS
            # ========================================
            {
                'name': 'On Fire!',
                'description': 'Complete tasks 3 days in a row',
                'icon': '🔥',
                'achievement_type': 'streak',
                'requirement': 3,
                'points': 30,
            },
            {
                'name': 'Week Warrior',
                'description': 'Complete tasks 7 days in a row',
                'icon': '⚡',
                'achievement_type': 'streak',
                'requirement': 7,
                'points': 70,
            },
            {
                'name': 'Consistency King',
                'description': 'Complete tasks 14 days in a row',
                'icon': '🏆',
                'achievement_type': 'streak',
                'requirement': 14,
                'points': 150,
            },
            {
                'name': 'Unstoppable',
                'description': 'Complete tasks 30 days in a row',
                'icon': '💎',
                'achievement_type': 'streak',
                'requirement': 30,
                'points': 300,
            },
            {
                'name': 'Legendary Streak',
                'description': 'Complete tasks 100 days in a row',
                'icon': '🌟',
                'achievement_type': 'streak',
                'requirement': 100,
                'points': 1000,
                'is_hidden': True,
            },
            
            # ========================================
            # CONSISTENCY ACHIEVEMENTS (Longest Streak)
            # ========================================
            {
                'name': 'Building Habits',
                'description': 'Reach a 5-day streak at any time',
                'icon': '🌱',
                'achievement_type': 'consistency',
                'requirement': 5,
                'points': 50,
            },
            {
                'name': 'Habit Master',
                'description': 'Reach a 21-day streak at any time',
                'icon': '🎖️',
                'achievement_type': 'consistency',
                'requirement': 21,
                'points': 210,
            },
            {
                'name': 'Iron Will',
                'description': 'Reach a 50-day streak at any time',
                'icon': '🛡️',
                'achievement_type': 'consistency',
                'requirement': 50,
                'points': 500,
            },
            
            # ========================================
            # SPECIAL ACHIEVEMENTS
            # ========================================
            {
                'name': 'Early Bird',
                'description': 'Complete a task before 8 AM',
                'icon': '🌅',
                'achievement_type': 'special',
                'requirement': 1,
                'points': 25,
            },
            {
                'name': 'Night Owl',
                'description': 'Complete a task after 10 PM',
                'icon': '🦉',
                'achievement_type': 'special',
                'requirement': 1,
                'points': 25,
            },
            {
                'name': 'Speed Demon',
                'description': 'Complete 10 tasks in one day',
                'icon': '🚀',
                'achievement_type': 'special',
                'requirement': 10,
                'points': 100,
            },
            {
                'name': 'Template Master',
                'description': 'Create your first custom template',
                'icon': '📋',
                'achievement_type': 'special',
                'requirement': 1,
                'points': 30,
            },
            {
                'name': 'Recurring Pro',
                'description': 'Create a recurring task',
                'icon': '🔄',
                'achievement_type': 'special',
                'requirement': 1,
                'points': 30,
            },
            {
                'name': 'Organizer',
                'description': 'Create 5 categories',
                'icon': '🏷️',
                'achievement_type': 'special',
                'requirement': 5,
                'points': 40,
            },
        ]
        
        created_count = 0
        for achievement_data in achievements:
            Achievement.objects.create(**achievement_data)
            created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'✅ Successfully created {created_count} achievements!'))
        self.stdout.write(self.style.SUCCESS('   🎯 Task completion badges'))
        self.stdout.write(self.style.SUCCESS('   🔥 Streak achievements'))
        self.stdout.write(self.style.SUCCESS('   🏆 Consistency rewards'))
        self.stdout.write(self.style.SUCCESS('   ⭐ Special achievements'))