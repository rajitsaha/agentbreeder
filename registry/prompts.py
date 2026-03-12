"""Prompt registry service — manages versioned prompt templates."""

from __future__ import annotations

import logging

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Prompt

logger = logging.getLogger(__name__)


class PromptRegistry:
    """Service class for prompt CRUD operations."""

    @staticmethod
    async def register(
        session: AsyncSession,
        name: str,
        version: str,
        content: str,
        description: str = "",
        team: str = "",
    ) -> Prompt:
        """Register or update a prompt in the registry."""
        stmt = select(Prompt).where(Prompt.name == name, Prompt.version == version)
        result = await session.execute(stmt)
        prompt = result.scalar_one_or_none()

        if prompt:
            prompt.content = content
            prompt.description = description
            prompt.team = team
            logger.info("Updated prompt '%s' v%s in registry", name, version)
        else:
            prompt = Prompt(
                name=name,
                version=version,
                content=content,
                description=description,
                team=team,
            )
            session.add(prompt)
            logger.info("Registered new prompt '%s' v%s in registry", name, version)

        await session.flush()
        return prompt

    @staticmethod
    async def list(
        session: AsyncSession,
        team: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Prompt], int]:
        """List prompts with optional filters."""
        stmt = select(Prompt)

        if team:
            stmt = stmt.where(Prompt.team == team)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Prompt.name, Prompt.version.desc())
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)

        result = await session.execute(stmt)
        prompts = list(result.scalars().all())

        return prompts, total

    @staticmethod
    async def get(session: AsyncSession, name: str, version: str | None = None) -> Prompt | None:
        """Get a prompt by name and optionally version (latest if not specified)."""
        stmt = select(Prompt).where(Prompt.name == name)
        if version:
            stmt = stmt.where(Prompt.version == version)
        else:
            stmt = stmt.order_by(Prompt.version.desc())
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_id(session: AsyncSession, prompt_id: str) -> Prompt | None:
        """Get a prompt by its UUID."""
        stmt = select(Prompt).where(Prompt.id == prompt_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update(
        session: AsyncSession,
        prompt_id: str,
        content: str | None = None,
        description: str | None = None,
    ) -> Prompt | None:
        """Update a prompt's content and/or description."""
        stmt = select(Prompt).where(Prompt.id == prompt_id)
        result = await session.execute(stmt)
        prompt = result.scalar_one_or_none()
        if not prompt:
            return None
        if content is not None:
            prompt.content = content
        if description is not None:
            prompt.description = description
        await session.flush()
        logger.info("Updated prompt '%s' v%s", prompt.name, prompt.version)
        return prompt

    @staticmethod
    async def delete(session: AsyncSession, prompt_id: str) -> bool:
        """Delete a prompt by id. Returns True if deleted."""
        stmt = select(Prompt).where(Prompt.id == prompt_id)
        result = await session.execute(stmt)
        prompt = result.scalar_one_or_none()
        if not prompt:
            return False
        await session.delete(prompt)
        await session.flush()
        logger.info("Deleted prompt '%s' v%s", prompt.name, prompt.version)
        return True

    @staticmethod
    async def get_versions(session: AsyncSession, prompt_id: str) -> list[Prompt]:
        """Get all versions of a prompt (looked up by the name of the given id)."""
        stmt = select(Prompt).where(Prompt.id == prompt_id)
        result = await session.execute(stmt)
        prompt = result.scalar_one_or_none()
        if not prompt:
            return []
        stmt = select(Prompt).where(Prompt.name == prompt.name).order_by(Prompt.version.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def duplicate(session: AsyncSession, prompt_id: str) -> Prompt | None:
        """Duplicate a prompt as a new version (bumps patch version)."""
        stmt = select(Prompt).where(Prompt.id == prompt_id)
        result = await session.execute(stmt)
        source = result.scalar_one_or_none()
        if not source:
            return None

        # Find the latest version for this prompt name to compute next version
        all_versions_stmt = (
            select(Prompt).where(Prompt.name == source.name).order_by(Prompt.version.desc())
        )
        all_result = await session.execute(all_versions_stmt)
        all_versions = list(all_result.scalars().all())

        latest_version = all_versions[0].version if all_versions else source.version
        parts = latest_version.split(".")
        try:
            parts[-1] = str(int(parts[-1]) + 1)
            new_version = ".".join(parts)
        except (ValueError, IndexError):
            new_version = latest_version + ".1"

        new_prompt = Prompt(
            name=source.name,
            version=new_version,
            content=source.content,
            description=source.description,
            team=source.team,
        )
        session.add(new_prompt)
        await session.flush()
        logger.info(
            "Duplicated prompt '%s' v%s -> v%s",
            source.name,
            source.version,
            new_version,
        )
        return new_prompt

    @staticmethod
    async def search(
        session: AsyncSession, query: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[Prompt], int]:
        """Search prompts by name or description."""
        pattern = f"%{query}%"
        stmt = select(Prompt).where(
            or_(Prompt.name.ilike(pattern), Prompt.description.ilike(pattern)),
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Prompt.name)
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)

        result = await session.execute(stmt)
        prompts = list(result.scalars().all())

        return prompts, total
