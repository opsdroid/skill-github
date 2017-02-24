from opsdroid.matchers import match_regex
import logging
import aiohttp


_LOGGER = logging.getLogger(__name__)
_GITHUB_API = "https://api.github.com"


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
