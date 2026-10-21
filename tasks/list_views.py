"""
Shared lists: a checklist several people can tick together (groceries, a
trip, chores). Owners invite people with a private link; the list page
checks for changes every few seconds so everyone sees the same thing.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .models import ListItem, SharedList
from .views import _json_body, replay_safe

MAX_ITEMS = 300
EMOJIS = ['🛒', '🏠', '✈️', '🎉', '📚', '💼', '🍳', '🎁', '🏋️', '🧹']


def _get_list(user, pk):
    """The list, if this user owns it or was invited. Anyone else gets a 404."""
    shared = get_object_or_404(SharedList.objects.select_related('owner'), pk=pk)
    if not shared.can_use(user):
        raise Http404
    return shared


def _short_name(user):
    return (user.first_name or user.username) if user else ''


def _person(user, owner_id):
    profile = getattr(user, 'profile', None)
    return {
        'id': user.id,
        'name': user.get_full_name() or user.username,
        # Only if they chose "Show email" in Privacy settings
        'email': user.email if profile is not None and profile.show_email else '',
        'owner': user.id == owner_id,
    }


def _state(shared, viewer):
    items = list(shared.items.select_related('added_by', 'done_by'))
    people = [shared.owner] + list(shared.members.select_related('profile').exclude(id=shared.owner_id))
    return {
        'id': shared.id,
        'name': shared.name,
        'emoji': shared.emoji,
        'is_owner': shared.owner_id == viewer.id,
        'version': shared.updated.isoformat(),
        'items': [
            # "by": who ticked it (if done) or who added it
            {'id': i.id, 'text': i.text, 'done': i.done, 'by': _short_name(i.done_by if i.done else i.added_by)}
            for i in items
        ],
        'members': [_person(p, shared.owner_id) for p in people],
    }


def _touch(shared):
    """Bump the list's 'updated' time so everyone's page knows to refresh."""
    shared.save(update_fields=['updated'])


@login_required
def lists_index(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()[:80]
        emoji = request.POST.get('emoji', '')
        if not name:
            messages.error(request, 'Give the list a name first.')
            return redirect('lists')
        shared = SharedList.objects.create(owner=request.user, name=name, emoji=emoji if emoji in EMOJIS else EMOJIS[0])
        return redirect('list_detail', pk=shared.pk)
    lists = []
    for shared in SharedList.visible_to(request.user).prefetch_related('items', 'members'):
        items = list(shared.items.all())
        lists.append({
            'obj': shared,
            'done': sum(1 for i in items if i.done),
            'total': len(items),
            'people': 1 + sum(1 for m in shared.members.all() if m.id != shared.owner_id),
            'mine': shared.owner_id == request.user.id,
        })
    return render(request, 'tasks/lists.html', {'lists': lists, 'emojis': EMOJIS})


@login_required
def list_detail(request, pk):
    shared = _get_list(request.user, pk)
    return render(request, 'tasks/list_detail.html', {
        'shared': shared,
        'state': _state(shared, request.user),
        'invite_url': request.build_absolute_uri(reverse('list_join', args=[shared.invite_token])),
    })


@login_required
@require_GET
def list_state(request, pk):
    response = JsonResponse(_state(_get_list(request.user, pk), request.user))
    response['Cache-Control'] = 'no-store'
    return response


@login_required
@require_POST
@replay_safe
def list_add_item(request, pk):
    shared = _get_list(request.user, pk)
    text = str(_json_body(request).get('text') or request.POST.get('text') or '').strip()[:200]
    if not text:
        return JsonResponse({'success': False, 'error': 'Type something to add.'}, status=400)
    if shared.items.count() >= MAX_ITEMS:
        return JsonResponse({'success': False, 'error': f'A list can hold up to {MAX_ITEMS} items. Clear the ticked ones first.'}, status=400)
    ListItem.objects.create(shared_list=shared, text=text, added_by=request.user)
    _touch(shared)
    return JsonResponse({'success': True, 'state': _state(shared, request.user)})


@login_required
@require_POST
@replay_safe
def list_toggle_item(request, item_id):
    item = get_object_or_404(ListItem.objects.select_related('shared_list'), pk=item_id)
    shared = _get_list(request.user, item.shared_list_id)
    wanted = _json_body(request).get('done')
    item.done = wanted if isinstance(wanted, bool) else not item.done
    item.done_by = request.user if item.done else None
    item.save(update_fields=['done', 'done_by'])
    _touch(shared)
    return JsonResponse({'success': True, 'state': _state(shared, request.user)})


@login_required
@require_POST
@replay_safe
def list_delete_item(request, item_id):
    item = ListItem.objects.filter(pk=item_id).select_related('shared_list').first()
    if item is None:
        # Already gone (someone else removed it): that's fine
        return JsonResponse({'success': True})
    shared = _get_list(request.user, item.shared_list_id)
    item.delete()
    _touch(shared)
    return JsonResponse({'success': True, 'state': _state(shared, request.user)})


@login_required
@require_POST
def list_clear_done(request, pk):
    shared = _get_list(request.user, pk)
    shared.items.filter(done=True).delete()
    _touch(shared)
    return JsonResponse({'success': True, 'state': _state(shared, request.user)})


@login_required
@require_POST
def list_manage(request, pk):
    """Rename, new invite link, remove someone, leave, or delete the list."""
    shared = _get_list(request.user, pk)
    action = request.POST.get('action')
    is_owner = shared.owner_id == request.user.id

    if action == 'leave' and not is_owner:
        shared.members.remove(request.user)
        messages.info(request, f'You left "{shared.name}".')
        return redirect('lists')
    if not is_owner:
        messages.error(request, 'Only the person who made this list can change that.')
        return redirect('list_detail', pk=shared.pk)

    if action == 'rename':
        name = request.POST.get('name', '').strip()[:80]
        emoji = request.POST.get('emoji', shared.emoji)
        if name:
            shared.name = name
            shared.emoji = emoji if emoji in EMOJIS else shared.emoji
            shared.save(update_fields=['name', 'emoji', 'updated'])
            messages.success(request, 'List renamed.')
    elif action == 'reset_link':
        from .models import _invite_token
        shared.invite_token = _invite_token()
        shared.save(update_fields=['invite_token', 'updated'])
        messages.success(request, 'New invite link made. The old one no longer works.')
    elif action == 'remove_member':
        try:
            shared.members.remove(int(request.POST.get('user_id', '')))
            _touch(shared)
            messages.info(request, 'Removed from the list.')
        except ValueError:
            pass
    elif action == 'delete':
        name = shared.name
        shared.delete()
        messages.success(request, f'Deleted "{name}".')
        return redirect('lists')
    return redirect('list_detail', pk=shared.pk)


@login_required
def list_join(request, token):
    """
    Opening an invite link shows who's inviting you; you only join when you
    tap Join (POST), so a link alone can never add someone to a list.
    """
    shared = get_object_or_404(SharedList.objects.select_related('owner'), invite_token=token)
    if shared.can_use(request.user):
        return redirect('list_detail', pk=shared.pk)
    allowed = getattr(request.user, 'profile', None) is None or request.user.profile.allow_shared_lists
    if request.method == 'POST' and allowed:
        with transaction.atomic():
            shared.members.add(request.user)
            _touch(shared)
        messages.success(request, f'You joined "{shared.name}".')
        return redirect('list_detail', pk=shared.pk)
    return render(request, 'tasks/list_join.html', {'shared': shared, 'allowed': allowed})
