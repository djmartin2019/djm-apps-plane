# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Regression tests for the cross-workspace / cross-project asset
authorization fixes (advisory cluster F)."""

import uuid

import pytest
from rest_framework import status

from plane.db.models import (
    FileAsset,
    Project,
    ProjectMember,
    User,
    Workspace,
    WorkspaceMember,
)


def make_asset(workspace, *, project=None, entity_type=None, is_uploaded=True):
    entity_type = entity_type or FileAsset.EntityTypeContext.ISSUE_ATTACHMENT
    return FileAsset.objects.create(
        asset=f"{workspace.id}/{uuid.uuid4().hex}-test.png",
        workspace=workspace,
        project=project,
        entity_type=entity_type,
        size=100,
        is_uploaded=is_uploaded,
        attributes={"name": "test.png", "type": "image/png", "size": 100},
    )


class AssetURLMixin:
    def workspace_asset_url(self, slug, asset_id=None):
        base = f"/api/assets/v2/workspaces/{slug}/"
        return f"{base}{asset_id}/" if asset_id else base

    def workspace_download_url(self, slug, asset_id):
        return f"/api/assets/v2/workspaces/{slug}/download/{asset_id}/"

    def duplicate_url(self, slug, asset_id):
        return f"/api/assets/v2/workspaces/{slug}/duplicate-assets/{asset_id}/"

    def project_bulk_url(self, slug, project_id, entity_id):
        return f"/api/assets/v2/workspaces/{slug}/projects/{project_id}/{entity_id}/bulk/"


@pytest.mark.contract
class TestWorkspaceFileAssetAuthz(AssetURLMixin):
    """WorkspaceFileAssetEndpoint previously had no membership check at all."""

    @pytest.mark.django_db
    def test_post_denied_for_non_member(self, session_client, workspace):
        outsider = User.objects.create_user(email="outsider@example.com", username="outsider")
        session_client.force_authenticate(user=outsider)

        response = session_client.post(
            self.workspace_asset_url(workspace.slug),
            {
                "name": "logo.png",
                "type": "image/png",
                "size": 100,
                "entity_type": "WORKSPACE_LOGO",
                "entity_identifier": str(workspace.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_logo_post_requires_admin(self, session_client, workspace):
        member = User.objects.create_user(email="member@example.com", username="member")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15, is_active=True)
        session_client.force_authenticate(user=member)

        response = session_client.post(
            self.workspace_asset_url(workspace.slug),
            {
                "name": "logo.png",
                "type": "image/png",
                "size": 100,
                "entity_type": "WORKSPACE_LOGO",
                "entity_identifier": str(workspace.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_get_denied_for_non_member(self, session_client, workspace):
        asset = make_asset(workspace)
        outsider = User.objects.create_user(email="outsider@example.com", username="outsider")
        session_client.force_authenticate(user=outsider)

        response = session_client.get(self.workspace_asset_url(workspace.slug, asset.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_get_secret_project_asset_denied_for_non_project_member(self, session_client, workspace):
        # Workspace member who is NOT a member of the (secret) project must not
        # be able to download that project's asset (GHSA-wrrw / GHSA-85h2).
        project = Project.objects.create(name="Secret", identifier="SEC", workspace=workspace, network=0)
        asset = make_asset(workspace, project=project)

        ws_member = User.objects.create_user(email="wsmember@example.com", username="wsmember")
        WorkspaceMember.objects.create(workspace=workspace, member=ws_member, role=15, is_active=True)
        session_client.force_authenticate(user=ws_member)

        response = session_client.get(self.workspace_asset_url(workspace.slug, asset.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_workspace_download_secret_project_asset_denied(self, session_client, workspace):
        project = Project.objects.create(name="Secret", identifier="SEC", workspace=workspace, network=0)
        asset = make_asset(workspace, project=project)

        ws_member = User.objects.create_user(email="wsmember@example.com", username="wsmember")
        WorkspaceMember.objects.create(workspace=workspace, member=ws_member, role=15, is_active=True)
        session_client.force_authenticate(user=ws_member)

        response = session_client.get(self.workspace_download_url(workspace.slug, asset.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.contract
class TestDuplicateAssetAuthz(AssetURLMixin):
    @pytest.mark.django_db
    def test_cross_workspace_duplication_denied(self, session_client, workspace, create_user):
        # Victim asset lives in `workspace` (attacker is not a member).
        victim_asset = make_asset(workspace)

        # Attacker controls their own workspace.
        attacker = User.objects.create_user(email="attacker@example.com", username="attacker")
        attacker_ws = Workspace.objects.create(name="Attacker", owner=attacker, slug="attacker-ws")
        WorkspaceMember.objects.create(workspace=attacker_ws, member=attacker, role=20, is_active=True)
        session_client.force_authenticate(user=attacker)

        before = FileAsset.objects.count()
        response = session_client.post(
            self.duplicate_url(attacker_ws.slug, victim_asset.id),
            {"entity_type": "ISSUE_ATTACHMENT"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        # No copy was created.
        assert FileAsset.objects.count() == before


@pytest.mark.contract
class TestProjectBulkAssetAuthz(AssetURLMixin):
    @pytest.mark.django_db
    def test_cross_project_reassignment_denied(self, session_client, workspace):
        attacker = User.objects.create_user(email="attacker@example.com", username="attacker")
        WorkspaceMember.objects.create(workspace=workspace, member=attacker, role=15, is_active=True)

        attacker_project = Project.objects.create(name="Attacker", identifier="ATK", workspace=workspace)
        ProjectMember.objects.create(project=attacker_project, member=attacker, role=20, is_active=True)

        victim_project = Project.objects.create(name="Victim", identifier="VIC", workspace=workspace)
        victim_asset = make_asset(
            workspace, project=victim_project, entity_type=FileAsset.EntityTypeContext.PROJECT_COVER
        )

        session_client.force_authenticate(user=attacker)
        response = session_client.post(
            self.project_bulk_url(workspace.slug, attacker_project.id, uuid.uuid4()),
            {"asset_ids": [str(victim_asset.id)]},
            format="json",
        )
        # Asset belongs to a different project -> not found, not reassigned.
        assert response.status_code == status.HTTP_404_NOT_FOUND
        victim_asset.refresh_from_db()
        assert victim_asset.project_id == victim_project.id

    @pytest.mark.django_db
    def test_same_project_reassignment_allowed(self, session_client, workspace):
        member = User.objects.create_user(email="member@example.com", username="member")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15, is_active=True)

        project = Project.objects.create(name="Mine", identifier="MIN", workspace=workspace)
        ProjectMember.objects.create(project=project, member=member, role=20, is_active=True)
        asset = make_asset(workspace, project=project, entity_type=FileAsset.EntityTypeContext.PROJECT_COVER)

        session_client.force_authenticate(user=member)
        response = session_client.post(
            self.project_bulk_url(workspace.slug, project.id, uuid.uuid4()),
            {"asset_ids": [str(asset.id)]},
            format="json",
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
