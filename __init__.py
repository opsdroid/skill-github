from opsdroid.matchers import match_regex, match_webhook
from opsdroid.message import Message
import logging
import aiohttp
import json
import random


_LOGGER = logging.getLogger(__name__)
_GITHUB_API = "https://api.github.com"

async def get_contributors(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                contributors = await resp.json()
                return len(contributors)
    return 0

async def selfmerge_shame(opsdroid, config, payload):
    message = Message("",
                      None,
                      config.get("room", opsdroid.default_connector.default_room),
                      opsdroid.default_connector)
    responses = [
        "Everyone look, {owner} just merged their own PR ({pr})! Naughty!!",
        "Oooo {owner} just merged their own PR ({pr}). I hope they had a good reason!",
        "Looks like {owner} has a bad habit of self merging. See {pr} for evidence!",
        "Someone should gently remind {owner} that self merging like in {pr} is not really ok..."
    ]
    if "action" in payload \
            and payload["action"] == "closed" \
            and "pull_request" in payload \
            and "merged_by" in payload["pull_request"]:
        owner = payload["pull_request"]["user"]["login"]
        merger = payload["pull_request"]["merged_by"]["login"]
        contributors = await get_contributors(payload["repository"]["contributors_url"])
        pr = "{}/{}#{}".format(payload["repository"]["owner"]["login"],
                               payload["repository"]["name"],
                               payload["pull_request"]["number"])

        if owner == merger and contributors > config.get("shame-selfmerges-contributor-threshold", 1):
            await message.respond(random.choice(responses).format(owner=merger, pr=pr))


@match_webhook('events')
async def github_events(opsdroid, config, message):
    request = await message.post()
    payload = json.loads(request["payload"])
    _LOGGER.debug(config.get("secret"))
    if config.get("shame-selfmerges", True):
        await selfmerge_shame(opsdroid, config, payload)


@match_regex(r'.*status.* (.+/.+#[0-9]+).*')
async def github_pr_status(opsdroid, config, message):
    # Split repo name
    full_pr = message.regex.group(1)
    owner, repo_pr = full_pr.split("/")
    repo, pr = repo_pr.split("#")

    # Request from GitHub API
    async with aiohttp.ClientSession() as session:
        url = "{}/repos/{}/{}/pulls/{}".format(_GITHUB_API, owner, repo, pr)
        _LOGGER.debug("Calling %s", url)
        async with session.get(url) as resp:
            _LOGGER.debug(resp.status)

            if resp.status == 200:
                pr_status = await resp.json()
                if pr_status["merged"]:
                    await message.respond("{} has been merged".format(full_pr))
                elif pr_status["mergeable"] == False:
                    await message.respond("{} has merge conflicts".format(full_pr))
                elif pr_status["mergeable"] and pr_status["mergeable_state"] == "unstable":
                    await message.respond("{} has failed or may still be running status checks".format(full_pr))
                elif pr_status["mergeable"] and pr_status["mergeable_state"] == "clean":
                    await message.respond("{} can be merged cleanly".format(full_pr))
                else:
                    await message.respond("{} is {}".format(full_pr, pr_status["state"]))

            elif resp.status == 404:
                await message.respond("Sorry I couldnt find {}".format(full_pr))
