#!/usr/bin/env bash
# exit on error
set -o errexit

echo "🔧 Installing dependencies..."
pip install -r requirements.txt

echo "📦 Collecting static files..."
python manage.py collectstatic --no-input --clear

echo "🗄️ Running migrations..."
python manage.py migrate --no-input

echo "🏷️ Creating default categories..."
python manage.py create_categories

echo "🏆 Creating default achievements..."
python manage.py create_achievements

echo "📋 Creating default templates..."
python manage.py create_default_templates

echo "✅ Build complete! All defaults loaded."