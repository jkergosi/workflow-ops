"""
Unit tests for the GitHub service - workflow syncing to GitHub repositories.
"""
import pytest
import json
import base64
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from github import GithubException

from app.services.github_service import GitHubService


class TestGitHubServiceInitialization:
    """Tests for GitHubService initialization and configuration."""

    @pytest.mark.unit
    def test_init_with_explicit_params(self):
        """GitHubService should accept explicit initialization parameters."""
        service = GitHubService(
            token="test-token",
            repo_owner="test-owner",
            repo_name="test-repo",
            branch="main"
        )

        assert service.token == "test-token"
        assert service.repo_owner == "test-owner"
        assert service.repo_name == "test-repo"
        assert service.branch == "main"

    @pytest.mark.unit
    def test_init_creates_github_client_when_token_provided(self):
        """GitHubService should create GitHub client when token is provided."""
        with patch("app.services.github_service.Github") as mock_github:
            service = GitHubService(token="test-token")
            mock_github.assert_called_once_with("test-token")
            assert service.github is not None

    @pytest.mark.unit
    def test_init_no_github_client_without_token(self):
        """GitHubService should not create GitHub client without token."""
        with patch("app.services.github_service.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = None
            mock_settings.GITHUB_REPO_OWNER = "owner"
            mock_settings.GITHUB_REPO_NAME = "repo"
            mock_settings.GITHUB_BRANCH = "main"

            service = GitHubService(token=None)
            assert service.github is None

    @pytest.mark.unit
    def test_repo_property_lazy_loads(self):
        """Repo property should lazy load the repository."""
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        service = GitHubService(
            token="token",
            repo_owner="owner",
            repo_name="repo",
            branch="main"
        )
        service.github = mock_github
        service._repo = None  # Reset cached repo

        # Access repo property
        result = service.repo

        mock_github.get_repo.assert_called_once_with("owner/repo")
        assert result == mock_repo

    @pytest.mark.unit
    def test_repo_property_returns_none_on_error(self):
        """Repo property should return None if repo cannot be accessed."""
        mock_github = MagicMock()
        mock_github.get_repo.side_effect = Exception("Access denied")

        service = GitHubService(
            token="token",
            repo_owner="owner",
            repo_name="repo",
            branch="main"
        )
        service.github = mock_github
        service._repo = None

        result = service.repo

        assert result is None


class TestGitHubServiceConfiguration:
    """Tests for GitHubService configuration checking."""

    @pytest.mark.unit
    def test_is_configured_true_when_all_params_set(self):
        """is_configured should return True when all parameters are set."""
        service = GitHubService(
            token="token",
            repo_owner="owner",
            repo_name="repo",
            branch="main"
        )

        assert service.is_configured() is True

    @pytest.mark.unit
    def test_is_configured_false_when_token_missing(self):
        """is_configured should return False when token is missing."""
        with patch("app.services.github_service.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = None
            mock_settings.GITHUB_REPO_OWNER = "owner"
            mock_settings.GITHUB_REPO_NAME = "repo"
            mock_settings.GITHUB_BRANCH = "main"

            service = GitHubService(
                token=None,
                repo_owner="owner",
                repo_name="repo",
                branch="main"
            )

            assert service.is_configured() is False

    @pytest.mark.unit
    def test_is_configured_false_when_repo_owner_missing(self):
        """is_configured should return False when repo_owner is missing."""
        with patch("app.services.github_service.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "token"
            mock_settings.GITHUB_REPO_OWNER = None
            mock_settings.GITHUB_REPO_NAME = "repo"
            mock_settings.GITHUB_BRANCH = "main"

            service = GitHubService(
                token="token",
                repo_owner=None,
                repo_name="repo",
                branch="main"
            )

            assert service.is_configured() is False

    @pytest.mark.unit
    def test_is_configured_false_when_repo_name_missing(self):
        """is_configured should return False when repo_name is missing."""
        with patch("app.services.github_service.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "token"
            mock_settings.GITHUB_REPO_OWNER = "owner"
            mock_settings.GITHUB_REPO_NAME = None
            mock_settings.GITHUB_BRANCH = "main"

            service = GitHubService(
                token="token",
                repo_owner="owner",
                repo_name=None,
                branch="main"
            )

            assert service.is_configured() is False

    @pytest.mark.unit
    def test_is_configured_false_when_branch_missing(self):
        """is_configured should return False when branch is missing."""
        with patch("app.services.github_service.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "token"
            mock_settings.GITHUB_REPO_OWNER = "owner"
            mock_settings.GITHUB_REPO_NAME = "repo"
            mock_settings.GITHUB_BRANCH = None

            service = GitHubService(
                token="token",
                repo_owner="owner",
                repo_name="repo",
                branch=None
            )

            assert service.is_configured() is False


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    @pytest.mark.unit
    def test_sanitize_normal_name(self):
        """Normal names should pass through with minimal changes."""
        service = GitHubService(token="t", repo_owner="o", repo_name="r", branch="b")

        result = service._sanitize_filename("My Workflow")

        assert result == "My Workflow"

    @pytest.mark.unit
    def test_sanitize_removes_invalid_characters(self):
        """Invalid characters should be replaced with underscores."""
        service = GitHubService(token="t", repo_owner="o", repo_name="r", branch="b")

        # Test various invalid characters
        result = service._sanitize_filename("Test<>:\"/\\|?*Workflow")

        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "/" not in result
        assert "\\" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    @pytest.mark.unit
    def test_sanitize_collapses_multiple_underscores(self):
        """Multiple underscores should be collapsed to one."""
        service = GitHubService(token="t", repo_owner="o", repo_name="r", branch="b")

        result = service._sanitize_filename("Test___Multiple___Underscores")

        assert "___" not in result
        assert "__" not in result

    @pytest.mark.unit
    def test_sanitize_strips_leading_trailing_spaces_and_dots(self):
        """Leading/trailing spaces and dots should be stripped."""
        service = GitHubService(token="t", repo_owner="o", repo_name="r", branch="b")

        result = service._sanitize_filename("  .Workflow Name.  ")

        assert not result.startswith(" ")
        assert not result.endswith(" ")
        assert not result.startswith(".")
        assert not result.endswith(".")

    @pytest.mark.unit
    def test_sanitize_empty_name_returns_default(self):
        """Empty name after sanitization should return default."""
        service = GitHubService(token="t", repo_owner="o", repo_name="r", branch="b")

        result = service._sanitize_filename("...")

        assert result == "unnamed_workflow"


class TestSyncWorkflowToGitHub:
    """Tests for syncing workflows to GitHub."""

    @pytest.fixture
    def configured_service(self):
        """Create a configured GitHubService with mocked repo."""
        service = GitHubService(
            token="token",
            repo_owner="owner",
            repo_name="repo",
            branch="main"
        )
        service._repo = MagicMock()
        return service

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sync_creates_new_file_when_not_exists(self, configured_service):
        """Should create new file when workflow doesn't exist in repo."""
        # Mock 404 error on get_contents (file not found)
        configured_service._repo.get_contents.side_effect = GithubException(404, {}, {})

        workflow_data = {"name": "Test", "nodes": [], "connections": {}}

        result = await configured_service.sync_workflow_to_github(
            workflow_id="wf-123",
            workflow_name="Test Workflow",
            workflow_data=workflow_data,
            environment_type="dev",
        )

        assert result is True
        configured_service._repo.create_file.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sync_updates_existing_file(self, configured_service):
        """Should update file when workflow exists in repo."""
        mock_file = MagicMock()
        mock_file.sha = "existing-sha"
        configured_service._repo.get_contents.return_value = mock_file

        workflow_data = {"name": "Test", "nodes": [], "connections": {}}

        result = await configured_service.sync_workflow_to_github(
            workflow_id="wf-123",
            workflow_name="Test Workflow",
            workflow_data=workflow_data,
            environment_type="dev",
        )

        assert result is True
        configured_service._repo.update_file.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sync_uses_environment_specific_path(self, configured_service):
        """Should use environment-type folder path."""
        configured_service._repo.get_contents.side_effect = GithubException(404, {}, {})

        workflow_data = {"name": "Test", "nodes": []}

        await configured_service.sync_workflow_to_github(
            workflow_id="wf-123",
            workflow_name="Test Workflow",
            workflow_data=workflow_data,
            environment_type="production",
        )

        # Check that create_file was called with correct path
        call_args = configured_service._repo.create_file.call_args
        assert "workflows/production/" in call_args.kwargs["path"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sync_uses_default_commit_message(self, configured_service):
        """Should use default commit message when none provided."""
        configured_service._repo.get_contents.side_effect = GithubException(404, {}, {})

        workflow_data = {"name": "Test", "nodes": []}

        await configured_service.sync_workflow_to_github(
            workflow_id="wf-123",
            workflow_name="Test Workflow",
            workflow_data=workflow_data,
            environment_type="dev",
        )

        call_args = configured_service._repo.create_file.call_args
        assert "Test Workflow" in call_args.kwargs["message"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sync_uses_custom_commit_message(self, configured_service):
        """Should use custom commit message when provided."""
        configured_service._repo.get_contents.side_effect = GithubException(404, {}, {})

        workflow_data = {"name": "Test", "nodes": []}

        await configured_service.sync_workflow_to_github(
            workflow_id="wf-123",
            workflow_name="Test Workflow",
            workflow_data=workflow_data,
            commit_message="Custom commit message",
            environment_type="dev",
        )

        call_args = configured_service._repo.create_file.call_args
        assert call_args.kwargs["message"] == "Custom commit message"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sync_adds_workflow_id_comment(self, configured_service):
        """Should add workflow ID comment to saved data."""
        configured_service._repo.get_contents.side_effect = GithubException(404, {}, {})

        workflow_data = {"name": "Test", "nodes": []}

        await configured_service.sync_workflow_to_github(
            workflow_id="wf-123",
            workflow_name="Test Workflow",
            workflow_data=workflow_data,
            environment_type="dev",
        )

        call_args = configured_service._repo.create_file.call_args
        content = call_args.kwargs["content"]
        parsed = json.loads(content)

        assert "_comment" in parsed
        assert "wf-123" in parsed["_comment"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sync_raises_when_not_configured(self):
        """Should raise ValueError when GitHub not configured."""
        service = GitHubService(token=None, repo_owner="o", repo_name="r", branch="b")

        with pytest.raises(ValueError, match="not properly configured"):
            await service.sync_workflow_to_github(
                workflow_id="wf-123",
                workflow_name="Test",
                workflow_data={},
                environment_type="dev",
            )

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sync_raises_on_github_error(self, configured_service):
        """Should re-raise GitHub errors (except 404)."""
        configured_service._repo.get_contents.side_effect = GithubException(403, {}, {})

        with pytest.raises(GithubException):
            await configured_service.sync_workflow_to_github(
                workflow_id="wf-123",
                workflow_name="Test",
                workflow_data={},
                environment_type="dev",
            )


class TestGetWorkflowById:
    """Tests for retrieving workflows from GitHub by workflow ID."""

    @pytest.fixture
    def configured_service(self):
        """Create a configured GitHubService with mocked repo."""
        service = GitHubService(
            token="token",
            repo_owner="owner",
            repo_name="repo",
            branch="main"
        )
        service._repo = MagicMock()
        return service

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_by_id_returns_workflow_with_commit_info(self, configured_service):
        """Should return workflow data with commit metadata."""
        from datetime import datetime

        workflow_data = {"id": "wf-123", "name": "Test Workflow", "nodes": [], "connections": {}}
        encoded_content = base64.b64encode(json.dumps(workflow_data).encode()).decode()

        mock_file = MagicMock()
        mock_file.content = encoded_content
        configured_service._repo.get_contents.return_value = mock_file

        mock_commit = MagicMock()
        mock_commit.sha = "abc123"
        mock_commit.commit.author.date = datetime(2024, 1, 15, 10, 0, 0)
        mock_commit.commit.message = "Update workflow"

        mock_commits = MagicMock()
        mock_commits.totalCount = 1
        mock_commits.__getitem__ = lambda self, idx: mock_commit
        configured_service._repo.get_commits.return_value = mock_commits

        result = await configured_service.get_workflow_by_id("wf-123", environment_type="dev")

        assert result is not None
        assert result["workflow"] == workflow_data
        assert result["commit_sha"] == "abc123"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_by_id_returns_none_when_not_found(self, configured_service):
        """Should return None when workflow not found."""
        configured_service._repo.get_contents.side_effect = GithubException(404, {}, {})

        result = await configured_service.get_workflow_by_id("wf-123", environment_type="dev")

        assert result is None


class TestGetAllWorkflowsFromGitHub:
    """Tests for retrieving all workflows from GitHub."""

    @pytest.fixture
    def configured_service(self):
        """Create a configured GitHubService with mocked repo."""
        service = GitHubService(
            token="token",
            repo_owner="owner",
            repo_name="repo",
            branch="main"
        )
        service._repo = MagicMock()
        return service

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_all_returns_dict_of_workflows(self, configured_service):
        """Should return dict mapping workflow_id to workflow data."""
        workflow1 = {"name": "Workflow 1", "id": "1"}
        workflow2 = {"name": "Workflow 2", "id": "2"}

        # Mock directory contents - need to include type attribute and base64-encoded content
        mock_file1 = MagicMock()
        mock_file1.name = "workflow1.json"
        mock_file1.path = "workflows/dev/workflow1.json"
        mock_file1.type = "file"
        mock_file1.content = base64.b64encode(json.dumps(workflow1).encode()).decode()

        mock_file2 = MagicMock()
        mock_file2.name = "workflow2.json"
        mock_file2.path = "workflows/dev/workflow2.json"
        mock_file2.type = "file"
        mock_file2.content = base64.b64encode(json.dumps(workflow2).encode()).decode()

        mock_readme = MagicMock()
        mock_readme.name = "README.md"
        mock_readme.type = "file"

        configured_service._repo.get_contents.return_value = [mock_file1, mock_file2, mock_readme]

        result = await configured_service.get_all_workflows_from_github(environment_type="dev")

        assert len(result) == 2
        assert "1" in result
        assert "2" in result
        assert result["1"]["name"] == "Workflow 1"
        assert result["2"]["name"] == "Workflow 2"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_all_skips_non_json_files(self, configured_service):
        """Should skip non-JSON files."""
        workflow = {"name": "Workflow 1", "id": "1"}

        mock_json = MagicMock()
        mock_json.name = "workflow.json"
        mock_json.path = "workflows/dev/workflow.json"
        mock_json.type = "file"
        mock_json.content = base64.b64encode(json.dumps(workflow).encode()).decode()

        mock_md = MagicMock()
        mock_md.name = "README.md"
        mock_md.type = "file"

        configured_service._repo.get_contents.return_value = [mock_json, mock_md]

        result = await configured_service.get_all_workflows_from_github(environment_type="dev")

        assert len(result) == 1
        assert "1" in result

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_all_returns_empty_when_not_configured(self):
        """Should return empty dict when not configured."""
        service = GitHubService(token=None, repo_owner="o", repo_name="r", branch="b")

        result = await service.get_all_workflows_from_github(environment_type="dev")

        assert result == {}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_all_returns_empty_on_github_error(self, configured_service):
        """Should return empty dict on GitHub error."""
        configured_service._repo.get_contents.side_effect = GithubException(404, {}, {})

        result = await configured_service.get_all_workflows_from_github(environment_type="dev")

        assert result == {}


class TestGetWorkflowByName:
    """Tests for retrieving workflow by name with commit info."""

    @pytest.fixture
    def configured_service(self):
        """Create a configured GitHubService with mocked repo."""
        service = GitHubService(
            token="token",
            repo_owner="owner",
            repo_name="repo",
            branch="main"
        )
        service._repo = MagicMock()
        return service

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_by_name_returns_workflow_with_commit_info(self, configured_service):
        """Should return workflow data with commit metadata."""
        from datetime import datetime

        workflow_data = {"name": "Test Workflow", "nodes": []}
        encoded = base64.b64encode(json.dumps(workflow_data).encode()).decode()

        mock_file = MagicMock()
        mock_file.name = "wf-123.json"
        mock_file.path = "workflows/dev/wf-123.json"
        mock_file.type = "file"
        mock_file.content = encoded

        mock_commit = MagicMock()
        mock_commit.sha = "abc123"
        mock_commit.commit.author.date = datetime(2024, 1, 15, 10, 0, 0)
        mock_commit.commit.message = "Update workflow"

        mock_commits = MagicMock()
        mock_commits.totalCount = 1
        mock_commits.__getitem__ = lambda self, idx: mock_commit

        configured_service._repo.get_contents.return_value = [mock_file]
        configured_service._repo.get_commits.return_value = mock_commits

        result = await configured_service.get_workflow_by_name("Test Workflow", environment_type="dev")

        assert result is not None
        assert result["workflow"] == workflow_data
        assert result["commit_sha"] == "abc123"
        assert result["commit_message"] == "Update workflow"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_by_name_uses_environment_type_folder(self, configured_service):
        """Should read from workflows/{environment_type}/."""
        configured_service._repo.get_contents.side_effect = GithubException(404, {}, {})

        await configured_service.get_workflow_by_name("Does Not Matter", environment_type="dev")

        call_args = configured_service._repo.get_contents.call_args
        assert call_args.args[0] == "workflows/dev"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_by_name_returns_none_when_not_found(self, configured_service):
        """Should return None when workflow not found."""
        configured_service._repo.get_contents.side_effect = GithubException(404, {}, {})

        result = await configured_service.get_workflow_by_name("Nonexistent", environment_type="dev")

        assert result is None


class TestGetWorkflowCommitInfo:
    """Tests for retrieving workflow commit info."""

    @pytest.fixture
    def configured_service(self):
        """Create a configured GitHubService with mocked repo."""
        service = GitHubService(
            token="token",
            repo_owner="owner",
            repo_name="repo",
            branch="main"
        )
        service._repo = MagicMock()
        return service

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_commit_info_returns_commit_details(self, configured_service):
        """Should return commit details for workflow."""
        from datetime import datetime

        mock_commit = MagicMock()
        mock_commit.sha = "def456"
        mock_commit.commit.author.date = datetime(2024, 1, 20)
        mock_commit.commit.message = "Fix bug"
        mock_commit.commit.author.name = "Developer"

        mock_commits = MagicMock()
        mock_commits.totalCount = 1
        mock_commits.__getitem__ = lambda self, idx: mock_commit

        workflow_data = {"name": "Test Workflow", "nodes": []}
        encoded = base64.b64encode(json.dumps(workflow_data).encode()).decode()

        mock_file = MagicMock()
        mock_file.name = "wf-123.json"
        mock_file.path = "workflows/dev/wf-123.json"
        mock_file.type = "file"
        mock_file.content = encoded

        configured_service._repo.get_contents.return_value = [mock_file]
        configured_service._repo.get_commits.return_value = mock_commits

        result = await configured_service.get_workflow_commit_info("Test Workflow", environment_type="dev")

        assert result["sha"] == "def456"
        assert result["message"] == "Fix bug"
        assert result["author"] is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_commit_info_returns_none_when_file_not_found(self, configured_service):
        """Should return None when file doesn't exist."""
        configured_service._repo.get_contents.side_effect = GithubException(404, {}, {})

        result = await configured_service.get_workflow_commit_info("Nonexistent", environment_type="dev")

        assert result is None


class TestDeleteWorkflowFromGitHub:
    """Tests for deleting workflows from GitHub."""

    @pytest.fixture
    def configured_service(self):
        """Create a configured GitHubService with mocked repo."""
        service = GitHubService(
            token="token",
            repo_owner="owner",
            repo_name="repo",
            branch="main"
        )
        service._repo = MagicMock()
        return service

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_delete_removes_file(self, configured_service):
        """Should delete workflow file from repo."""
        mock_file = MagicMock()
        mock_file.sha = "file-sha"
        configured_service._repo.get_contents.return_value = mock_file

        result = await configured_service.delete_workflow_from_github(
            workflow_id="wf-123",
            workflow_name="Test Workflow",
            environment_type="dev",
        )

        assert result is True
        configured_service._repo.delete_file.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_delete_returns_true_when_file_not_found(self, configured_service):
        """Should return True when file already doesn't exist."""
        configured_service._repo.get_contents.side_effect = GithubException(404, {}, {})

        result = await configured_service.delete_workflow_from_github(
            workflow_id="wf-123",
            workflow_name="Test",
            environment_type="dev",
        )

        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_delete_raises_when_not_configured(self):
        """Should raise ValueError when not configured."""
        service = GitHubService(token=None, repo_owner="o", repo_name="r", branch="b")

        with pytest.raises(ValueError, match="not properly configured"):
            await service.delete_workflow_from_github("wf-123", "Test")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_delete_uses_custom_commit_message(self, configured_service):
        """Should use custom commit message when provided."""
        mock_file = MagicMock()
        mock_file.sha = "sha"
        configured_service._repo.get_contents.return_value = mock_file

        await configured_service.delete_workflow_from_github(
            workflow_id="wf-123",
            workflow_name="Test",
            commit_message="Custom delete message",
            environment_type="dev",
        )

        call_args = configured_service._repo.delete_file.call_args
        assert call_args.kwargs["message"] == "Custom delete message"


class TestTestConnection:
    """Tests for testing GitHub connection."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_connection_returns_true_on_success(self):
        """Should return True when connection succeeds."""
        service = GitHubService(
            token="token",
            repo_owner="owner",
            repo_name="repo",
            branch="main"
        )
        service._repo = MagicMock()
        service._repo.get_branch.return_value = MagicMock()

        result = await service.test_connection()

        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_connection_returns_false_when_not_configured(self):
        """Should return False when not configured."""
        service = GitHubService(token=None, repo_owner="o", repo_name="r", branch="b")

        result = await service.test_connection()

        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_connection_returns_false_on_error(self):
        """Should return False when connection fails."""
        service = GitHubService(
            token="token",
            repo_owner="owner",
            repo_name="repo",
            branch="main"
        )
        service._repo = MagicMock()
        service._repo.get_branch.side_effect = Exception("Connection failed")

        result = await service.test_connection()

        assert result is False
