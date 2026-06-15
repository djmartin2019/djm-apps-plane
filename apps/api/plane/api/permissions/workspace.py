# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework.permissions import BasePermission, SAFE_METHODS

from plane.app.permissions import ROLE
from plane.db.models import WorkspaceMember


def get_workspace_slug(view):
    """Resolve the workspace slug from the view, returning None when it is absent.

    Accessing ``view.workspace_slug`` directly would raise ``AttributeError`` (and a
    500) on a view that does not expose it; returning None lets the caller deny cleanly.
    """
    return getattr(view, "workspace_slug", None)


class WorkspaceAdminOnlyPermission(BasePermission):
    """
    Permission class for external APIs that restricts access to workspace admins only.
    """

    def has_permission(self, request, view):
        """Allow only active workspace admins."""
        if request.user.is_anonymous:
            return False

        workspace_slug = get_workspace_slug(view)
        if not workspace_slug:
            return False

        return WorkspaceMember.objects.filter(
            member=request.user,
            workspace__slug=workspace_slug,
            role=ROLE.ADMIN.value,
            is_active=True,
        ).exists()


class WorkspaceAdminWriteMemberReadPermission(BasePermission):
    """
    Permission class for external APIs that allows workspace members to read
    but restricts write operations to workspace admins only.
    """

    def has_permission(self, request, view):
        """Allow active members to read and restrict writes to active admins."""
        if request.user.is_anonymous:
            return False

        workspace_slug = get_workspace_slug(view)
        if not workspace_slug:
            return False

        if request.method in SAFE_METHODS:
            return WorkspaceMember.objects.filter(
                member=request.user,
                workspace__slug=workspace_slug,
                role__in=[ROLE.ADMIN.value, ROLE.MEMBER.value],
                is_active=True,
            ).exists()

        return WorkspaceMember.objects.filter(
            member=request.user,
            workspace__slug=workspace_slug,
            role=ROLE.ADMIN.value,
            is_active=True,
        ).exists()
