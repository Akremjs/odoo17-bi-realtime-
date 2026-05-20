# -*- coding: utf-8 -*-
"""Utilitaires partagés du module bi_realtime."""

DEFAULT_AI_API_URL = 'http://host.docker.internal:8000'


def get_ai_api_url(env):
    """URL de l'API IA (paramètre système ou défaut Docker)."""
    url = (
        env['ir.config_parameter']
        .sudo()
        .get_param('bi_realtime.ai_api_url', '')
        .strip()
    )
    return (url or DEFAULT_AI_API_URL).rstrip('/')
