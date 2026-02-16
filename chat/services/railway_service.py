"""
Railway Deployment Monitoring Service

Integrates with Railway GraphQL API to track deployment status after publishing changes.
Requires environment variables:
- RAILWAY_API_TOKEN: Your Railway API token
- RAILWAY_PROJECT_ID: The project ID for the Astro site
- RAILWAY_ENVIRONMENT_ID: Optional, defaults to 'production'
"""

import logging
import time
from typing import Optional, Tuple, Dict
from datetime import datetime

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Railway GraphQL API endpoint
RAILWAY_API_URL = 'https://backboard.railway.app/graphql'

# Deployment status mapping
# Railway statuses: BUILDING, DEPLOYING, SUCCESS, FAILED, CRASHED, REMOVED, INITIALIZING
RAILWAY_STATUS_MAP = {
    'SUCCESS': 'success',
    'FAILED': 'failed',
    'CRASHED': 'failed',
    'REMOVED': 'failed',
    'BUILDING': 'pending',
    'DEPLOYING': 'pending',
    'INITIALIZING': 'pending',
}


def _get_api_token() -> Optional[str]:
    """Get Railway API token from settings."""
    token = getattr(settings, 'RAILWAY_API_TOKEN', None)
    if not token:
        logger.warning('RAILWAY_API_TOKEN not configured')
    return token


def _get_project_id() -> Optional[str]:
    """Get Railway project ID from settings."""
    project_id = getattr(settings, 'RAILWAY_PROJECT_ID', None)
    if not project_id:
        logger.warning('RAILWAY_PROJECT_ID not configured')
    return project_id


def _get_environment_id() -> Optional[str]:
    """Get Railway environment ID from settings, defaults to 'production'."""
    return getattr(settings, 'RAILWAY_ENVIRONMENT_ID', 'production')


def _graphql_request(query: str, variables: Optional[Dict] = None) -> Optional[Dict]:
    """
    Make a GraphQL request to Railway API.

    Args:
        query: GraphQL query string
        variables: Optional query variables

    Returns:
        Response data dict or None on error
    """
    token = _get_api_token()
    if not token:
        return None

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    payload = {'query': query}
    if variables:
        payload['variables'] = variables

    try:
        response = requests.post(
            RAILWAY_API_URL,
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        if 'errors' in data:
            logger.error('Railway API errors: %s', data['errors'])
            return None

        return data.get('data')

    except requests.RequestException as e:
        logger.exception('Railway API request failed: %s', e)
        return None


def get_latest_deployment(
    project_id: Optional[str] = None,
    environment: Optional[str] = None,
) -> Optional[str]:
    """
    Get the latest deployment ID for a Railway project environment.

    Args:
        project_id: Railway project ID (uses RAILWAY_PROJECT_ID if not provided)
        environment: Environment name (uses RAILWAY_ENVIRONMENT_ID if not provided)

    Returns:
        Deployment ID string or None if not found
    """
    project_id = project_id or _get_project_id()
    environment = environment or _get_environment_id()

    if not project_id:
        logger.warning('Cannot get latest deployment: project_id not configured')
        return None

    query = """
    query GetLatestDeployment($projectId: String!, $environmentName: String!) {
      project(id: $projectId) {
        environments(name: $environmentName) {
          edges {
            node {
              deployments(first: 1, orderBy: {field: CREATED_AT, direction: DESC}) {
                edges {
                  node {
                    id
                    status
                    createdAt
                  }
                }
              }
            }
          }
        }
      }
    }
    """

    variables = {
        'projectId': project_id,
        'environmentName': environment,
    }

    data = _graphql_request(query, variables)
    if not data:
        return None

    try:
        # Navigate nested structure
        environments = data['project']['environments']['edges']
        if not environments:
            logger.warning('No environments found for project %s', project_id)
            return None

        deployments = environments[0]['node']['deployments']['edges']
        if not deployments:
            logger.info('No deployments found for project %s', project_id)
            return None

        deployment = deployments[0]['node']
        deployment_id = deployment['id']

        logger.info(
            'Found latest deployment: %s (status: %s, created: %s)',
            deployment_id,
            deployment.get('status'),
            deployment.get('createdAt'),
        )

        return deployment_id

    except (KeyError, IndexError, TypeError) as e:
        logger.exception('Failed to parse deployment data: %s', e)
        return None


def get_deployment_status(deployment_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Get the current status of a Railway deployment.

    Args:
        deployment_id: Railway deployment ID

    Returns:
        Tuple of (normalized_status, error_message)
        - normalized_status: 'pending', 'success', 'failed', or None
        - error_message: Error details if status is 'failed', otherwise None
    """
    if not _get_api_token():
        return (None, None)

    query = """
    query GetDeploymentStatus($deploymentId: String!) {
      deployment(id: $deploymentId) {
        id
        status
        createdAt
        completedAt
        meta
      }
    }
    """

    variables = {'deploymentId': deployment_id}
    data = _graphql_request(query, variables)

    if not data or 'deployment' not in data:
        return (None, None)

    deployment = data['deployment']
    railway_status = deployment.get('status')

    if not railway_status:
        return (None, None)

    # Normalize status
    normalized_status = RAILWAY_STATUS_MAP.get(railway_status, 'pending')

    # Extract error message for failed deployments
    error_message = None
    if normalized_status == 'failed':
        meta = deployment.get('meta', {})
        # Railway stores error details in meta field
        if isinstance(meta, dict):
            error_message = meta.get('errorMessage', f'Deployment {railway_status.lower()}')
        else:
            error_message = f'Deployment {railway_status.lower()}'

    logger.debug(
        'Deployment %s status: %s (Railway: %s)',
        deployment_id[:8],
        normalized_status,
        railway_status,
    )

    return (normalized_status, error_message)


def wait_for_deployment_completion(
    deployment_id: str,
    timeout: int = 600,
    poll_interval: int = 10,
) -> Tuple[str, Optional[str]]:
    """
    Poll deployment status until it completes or times out.

    Args:
        deployment_id: Railway deployment ID
        timeout: Maximum wait time in seconds (default: 600 = 10 minutes)
        poll_interval: Seconds between status checks (default: 10)

    Returns:
        Tuple of (final_status, error_message)
        - final_status: 'success', 'failed', or 'timeout'
        - error_message: Error details if failed, otherwise None
    """
    start_time = time.time()

    logger.info(
        'Waiting for deployment %s to complete (timeout: %ds)',
        deployment_id[:8],
        timeout,
    )

    while True:
        elapsed = time.time() - start_time

        if elapsed >= timeout:
            logger.warning(
                'Deployment %s timed out after %ds',
                deployment_id[:8],
                elapsed,
            )
            return ('timeout', f'Deployment monitoring timed out after {timeout}s')

        # Check status
        status, error_message = get_deployment_status(deployment_id)

        if status is None:
            # API error - wait and retry
            logger.debug('Failed to get deployment status, retrying...')
            time.sleep(poll_interval)
            continue

        if status == 'success':
            logger.info('Deployment %s succeeded', deployment_id[:8])
            return ('success', None)

        if status == 'failed':
            logger.warning('Deployment %s failed: %s', deployment_id[:8], error_message)
            return ('failed', error_message)

        # Still pending - wait and retry
        logger.debug('Deployment %s still pending, waiting %ds...', deployment_id[:8], poll_interval)
        time.sleep(poll_interval)


def is_railway_configured() -> bool:
    """Check if Railway API credentials are configured."""
    return bool(_get_api_token() and _get_project_id())
