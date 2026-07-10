import os
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from jira import JIRA
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
DEFAULT_PROJECT_KEY = os.getenv("DEFAULT_PROJECT_KEY", "")

jira_client = JIRA(server=JIRA_URL, basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN))


def resolve_project_key(input_key: Optional[str]) -> str:
    if input_key:
        candidate = input_key.strip()
        try:
            proj = jira_client.project(candidate.upper())
            return proj.key
        except Exception:
            try:
                projects = jira_client.projects()
            except Exception:
                projects = []

            lowered = candidate.lower()
            for p in projects:
                if p.name.lower() == lowered or p.key.lower() == lowered:
                    return p.key

            for p in projects:
                if lowered in p.name.lower() or lowered in p.key.lower():
                    return p.key

    if DEFAULT_PROJECT_KEY:
        try:
            proj = jira_client.project(DEFAULT_PROJECT_KEY.upper())
            return proj.key
        except Exception:
            pass

    try:
        projects = jira_client.projects()
        if projects:
            return projects[0].key
    except Exception:
        pass

    raise RuntimeError("No accessible Jira project found and no default is configured.")

# Initialize Discord Bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# ----------------------------------------------------
# READ COMMAND: Fetch an Issue
# ----------------------------------------------------
@bot.tree.command(name="jira_get", description="Fetch details of a Jira issue.")
@app_commands.describe(issue_key="The Jira Key (e.g., PROJ-123)")
async def jira_get(interaction: discord.Interaction, issue_key: str):
    # CRITICAL: Defer response immediately to avoid the 3-second timeout rule
    await interaction.response.defer()
    
    try:
        issue = jira_client.issue(issue_key)
        summary = issue.fields.summary
        status = issue.fields.status.name
        description = issue.fields.description or "No description provided."
        assignee = issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned"
        
        embed = discord.Embed(
            title=f"[{issue_key}] {summary}", 
            url=f"{JIRA_URL}/browse/{issue_key}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Assignee", value=assignee, inline=True)
        embed.add_field(name="Description", value=description[:1024], inline=False)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"Error fetching issue `{issue_key}`. Check if the key exists.")

# ----------------------------------------------------
# WRITE COMMAND: Create an Issue
# ----------------------------------------------------
@bot.tree.command(name="jira_create", description="Create a new Jira issue.")
@app_commands.describe(project_key="Project Code or name (optional; accepts partial)", summary="Issue Title", description="Detailed summary", issuetype="Issue type (Task, Bug, Story)")
async def jira_create(interaction: discord.Interaction, project_key: str = "", summary: str = "", description: str = "", issuetype: str = "Task"):
    await interaction.response.defer()
    
    try:
        resolved_key = resolve_project_key(project_key or None)
    except Exception as e:
        await interaction.followup.send(f"Could not determine a Jira project. {e}")
        return

    issue_dict = {
        'project': {'key': resolved_key},
        'summary': summary or "(no summary)",
        'description': description or "No description provided.",
        'issuetype': {'name': issuetype or 'Task'},
    }
    
    try:
        new_issue = jira_client.create_issue(fields=issue_dict)
        
        embed = discord.Embed(
            title="✅ Issue Created Successfully",
            description=f"Created **[{new_issue.key}]** - {summary}",
            url=f"{JIRA_URL}/browse/{new_issue.key}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"Failed to create issue. Ensure the project and issue type are valid. ({e})")

bot.run(DISCORD_TOKEN)