"""
Huddle Context Injection for AlumniHuddle Chat

This module provides functions to inject huddle-specific context (including mentor data)
into chat conversations. When a user from a specific huddle starts a chat, this module
ensures Claude has access to the mentor directory for that huddle.
"""

import logging
from typing import Optional, Dict, Any, List

from fastapi import Request

from open_webui.models.mentors import Mentors, MentorProfileModel
from open_webui.models.tenants import HuddleModel
from open_webui.models.users import Users

log = logging.getLogger(__name__)


def apply_huddle_assignment(
    huddle_id: Optional[str],
    user_id: str,
    db=None,
) -> None:
    """
    Assign a user to a huddle by setting their tenant_id.

    This is called after user creation to automatically associate them
    with the huddle they signed up from (based on subdomain).

    Args:
        huddle_id: ID of the huddle to assign the user to (from request.state.huddle)
        user_id: ID of the user to assign
        db: Optional database session
    """
    if huddle_id:
        try:
            Users.update_user_by_id(user_id, {"tenant_id": huddle_id}, db=db)
            log.info(f"AlumniHuddle: Assigned user {user_id} to huddle {huddle_id}")
        except Exception as e:
            log.error(
                f"Failed to assign user {user_id} to huddle {huddle_id}: {e}"
            )


def get_mentor_context_for_huddle(huddle: HuddleModel, limit: int = 200) -> str:
    """
    Generate a mentor context string for a specific huddle.

    Args:
        huddle: The HuddleModel for the current tenant
        limit: Maximum number of mentors to include

    Returns:
        A formatted string containing mentor information
    """
    try:
        mentors = Mentors.get_mentors_by_huddle(huddle.id, limit=limit)

        if not mentors:
            return ""

        mentor_entries = []
        for mentor in mentors:
            entry = format_mentor_entry(mentor, huddle.slug)
            mentor_entries.append(entry)

        return "\n\n".join(mentor_entries)

    except Exception as e:
        log.error(f"Error fetching mentors for huddle {huddle.id}: {e}")
        return ""


def format_mentor_entry(mentor: MentorProfileModel, huddle_slug: str) -> str:
    """
    Format a single mentor's information for the context.
    Uses the strict output format: Name – Class Year / Title, Company (Industry)

    Args:
        mentor: The mentor profile model
        huddle_slug: The huddle slug for building profile URLs
    """
    # Build header line
    header_parts = [mentor.full_name, f"Class of {mentor.class_year}"]
    if mentor.title and mentor.current_company:
        header_parts.append(f"{mentor.title}, {mentor.current_company}")
    elif mentor.title:
        header_parts.append(mentor.title)
    elif mentor.current_company:
        header_parts.append(mentor.current_company)
    if mentor.industry:
        header_parts.append(f"({mentor.industry})")

    parts = [" – ".join(header_parts[:2]) + (" / " + " ".join(header_parts[2:]) if len(header_parts) > 2 else "")]

    parts.append(f"  Location: {mentor.metro_area}")

    # Add profile deep link
    parts.append(f"  Profile: https://alumnihuddle.vercel.app/{huddle_slug}/profile/{mentor.id}")

    if mentor.linkedin_url and mentor.linkedin_url.strip() and mentor.linkedin_url.strip() != "www.linkedin.com/in/":
        parts.append(f"  LinkedIn: {mentor.linkedin_url}")

    if mentor.skills_experience:
        skills = mentor.skills_experience
        if len(skills) > 200:
            skills = skills[:200] + "..."
        parts.append(f"  Skills & Expertise: {skills}")

    if mentor.prior_roles:
        prior = mentor.prior_roles
        if len(prior) > 150:
            prior = prior[:150] + "..."
        parts.append(f"  Prior Experience: {prior}")

    return "\n".join(parts)


def build_huddle_system_prompt(huddle: HuddleModel) -> str:
    """
    Build the complete system prompt for a huddle.

    Adapted from the proven AlumniHuddle Mentor Matcher prompt,
    now dynamic per-huddle with tenant-aware context.
    """
    mentor_context = get_mentor_context_for_huddle(huddle)
    mentor_count = Mentors.get_mentor_count_by_huddle(huddle.id)
    directory_url = f"https://{huddle.slug}.alumnihuddle.com"

    prompt = f"""You are AlumniHuddle Mentor Matcher, an assistant that helps members of {huddle.name} connect with the best possible alumni mentors and provides career coaching when appropriate.

## AUTHORITATIVE KNOWLEDGE BASE CONTEXT (CRITICAL)

You have read-only access to a verified and authoritative AlumniHuddle mentor database. This database contains alumni mentors from the {huddle.name} network and includes, when available: full name, class year, current job title, current company, industry, location, LinkedIn profile URL, skills/expertise, and prior experience.

Unless the user explicitly states otherwise, ALWAYS assume:
- The mentor pool is {huddle.name} alumni
- The database is complete, verified, and authoritative
- You should proceed directly to mentor recommendations once intake information is sufficient

Important behavior rules:
- Never say you "cannot access the file," "cannot access the database," or that the environment limits access
- Never mention internal constraints or system mechanics

## IMPORTANT GOAL

Deliver a smooth, confident experience with minimal friction. Gather information efficiently without making the user feel constrained or rushed.

## CORE BEHAVIOR

- Begin with a short, warm welcome
- If the user starts with a specific request (e.g. "Help me find a mentor"), immediately begin that flow
- Keep tone conversational, encouraging, and confident
- Ask clarifying questions only when they materially improve mentor quality

## MENTOR MATCHING FLOW

### Initial Intake

When the user wants a mentor match, ask:

"Great — I can help with that. To get you the best matches, tell me a bit about you:

I'm a [year] studying [what you studied]. I've done [key internships, jobs, or projects]. I'm interested in [roles or industries]. I'm open to working in [cities]. I'd love a mentor who can help with [recruiting, career clarity, skill-building, networking, etc.].

You can also paste your resume if you'd like — totally optional."

Proceed once reasonable information is provided. Do not enforce formatting.

### Light Clarification

If goals are broad or exploratory, ask one gentle clarifying question, for example:
"Before I finalize mentor recommendations, would you like to narrow things slightly within finance, consulting, or tech — or keep it broad and exploratory?"

If the user is unsure, proceed with broad exploration-friendly mentors by default.

## MENTOR RECOMMENDATIONS

Recommend 3 to 5 mentors from the knowledge base.

### Experience Mix (when available)
- At least one senior alum (~10+ years experience)
- At least one recent graduate who can speak to recruiting and early-career decisions
- Relevance always outweighs variety

### Selection Criteria (priority order)
1. Industry alignment
2. Career path relevance
3. Experience level and seniority
4. Shared academics, athletics, clubs, or work experience
5. Location fit
6. Class year proximity (secondary signal only)

### Mentor Output Format (STRICT)

For each mentor, present the information in this order:

**Full Name** – Class Year / Current Job Title, Current Company (Industry)

[View Full Profile](profile URL from the database)
LinkedIn: [LinkedIn profile URL] (only if a verified URL exists in the database — never guess or construct URLs)

A short paragraph explaining:
- Why their career path is relevant
- What perspective they offer (senior vs recent)
- Any meaningful shared background or overlap

### Absolute Rules
- Never invent mentors
- Never guess job titles, companies, industries, or LinkedIn URLs
- Always include the profile link from the database for each mentor recommendation
- If any detail (including LinkedIn) is missing, simply omit it or acknowledge briefly

## CONVERSATION SUPPORT

After mentor recommendations, include:

### Conversation Starters
1–2 tailored opening messages per mentor

### First-Call Agenda
3–4 bullets designed for a 15–20 minute intro call

### Outreach Email Template
Friendly, concise, copy-paste ready

### Contact Info Note (required)
"You can find each mentor's contact information directly in your AlumniHuddle directory: {directory_url}"

## NEXT STEPS

End with a short, friendly set of options:
- Adjust goals, roles, or locations
- Refine the list (more senior, more recent grads, specific firms)
- Career coaching (resume feedback, interview prep, exploration)
- Tighten or personalize outreach messages

## CAREER COACHING FLOW

If the user wants coaching only:
- Ask them to describe their goal in their own words
- Provide focused, actionable guidance
- Avoid unnecessary follow-ups

## GUARDRAILS

- Never invent mentors or details
- Never mention internal constraints or system mechanics
- Keep responses concise, specific, and human
- When information is sufficient, proceed confidently

"""

    if mentor_context:
        prompt += f"""## MENTOR DATABASE ({mentor_count} mentors available)

The following is the complete mentor directory for {huddle.name}. Use this data to make recommendations.

{mentor_context}
"""
    else:
        prompt += f"""## NOTE

The mentor directory for {huddle.name} is currently being set up. Help members with general career advice for now.
"""

    return prompt


def get_huddle_from_request(request: Request) -> Optional[HuddleModel]:
    """
    Extract the current huddle from the request state.

    The TenantMiddleware sets this on request.state.huddle
    """
    return getattr(request.state, "huddle", None)


def inject_huddle_context(
    request: Request,
    messages: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Inject huddle-specific context into the chat messages.

    This function:
    1. Checks if the request is from a specific huddle
    2. If so, adds/updates the system message with huddle context

    Args:
        request: The FastAPI request object
        messages: The list of chat messages
        metadata: Optional metadata dict

    Returns:
        Updated messages list with huddle context injected
    """
    huddle = get_huddle_from_request(request)

    if not huddle:
        log.debug("No huddle context found, skipping injection")
        return messages

    log.info(f"Injecting context for huddle: {huddle.name}")

    # Build the huddle-specific system prompt
    huddle_system_prompt = build_huddle_system_prompt(huddle)

    # Check if there's already a system message
    has_system = any(msg.get("role") == "system" for msg in messages)

    if has_system:
        # Prepend huddle context to existing system message
        for msg in messages:
            if msg.get("role") == "system":
                existing_content = msg.get("content", "")
                msg["content"] = f"{huddle_system_prompt}\n\n---\n\n{existing_content}"
                break
    else:
        # Add new system message at the beginning
        messages.insert(0, {
            "role": "system",
            "content": huddle_system_prompt
        })

    return messages
