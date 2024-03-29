import json
import os
import nextcord
from nextcord.ext import commands
from util.economy_system import get_points, set_points, get_steam_id
from util.rconutility import RconUtility
import asyncio

class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.load_shop_items()
        self.load_config()
        self.load_economy()
        self.rcon_util = RconUtility(self.servers)

    def load_config(self):
        config_path = "config.json"
        with open(config_path) as config_file:
            config = json.load(config_file)
            self.servers = config["PALWORLD_SERVERS"]

    def load_economy(self):
        config_path = "config.json"
        with open(config_path) as config_file:
            self.economy_config = json.load(config_file)
        self.economy_config = self.economy_config.get("ECONOMY_SETTINGS", {})
        self.currency = self.economy_config.get("currency", "points")

    def load_shop_items(self):
        config_path = "gamedata"
        shop_items_path = os.path.join(config_path, "kits.json")
        with open(shop_items_path) as shop_items_file:
            self.shop_items = json.load(shop_items_file)

    @nextcord.slash_command(name="shop", description="Shop commands.")
    async def shop(self, _interaction: nextcord.Interaction):
        pass

    @shop.subcommand(name="menu", description="Displays available items in the shop.")
    async def menu(self, interaction: nextcord.Interaction):
        embed = nextcord.Embed(title="Shop Items", color=nextcord.Color.blue())
        for item_name, item_info in self.shop_items.items():
            embed.add_field(
                name=item_name,
                value=f"{item_info['description']} \n **Price:** {item_info['price']} {self.currency}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @shop.subcommand(name="redeem", description="Redeem your points for a shop item.")
    async def redeem(
        self,
        interaction: nextcord.Interaction,
        item_name: str = nextcord.SlashOption(
            description="The name of the item to redeem.", autocomplete=True
        ),
        server: str = nextcord.SlashOption(
            description="Select a server", autocomplete=True
        ),
    ):
        await interaction.response.defer()
        user_id = str(interaction.user.id)
        user_name = interaction.user.display_name

        data = get_points(user_id, user_name)
        if not data:
            await interaction.followup.send(
                "There was an error retrieving your data.", ephemeral=True
            )
            return

        user_name, points = data
        steam_id = get_steam_id(user_id)

        if steam_id is None:
            await interaction.followup.send("No Steam ID linked.", ephemeral=True)
            return

        item = self.shop_items.get(item_name)
        if not item:
            await interaction.followup.send("Item not found.", ephemeral=True)
            return

        if points < item["price"]:
            await interaction.followup.send(
                f"You do not have enough {self.currency} to redeem this item.",
                ephemeral=True,
            )
            return

        new_points = points - item["price"]
        set_points(user_id, user_name, new_points)

        for command_template in item["commands"]:
            command = command_template.format(steamid=steam_id)
            asyncio.create_task(self.rcon_util.rcon_command(server, command))
            await asyncio.sleep(1)

        embed = nextcord.Embed(
            title=f"Redeemed {item_name}",
            description=f"Successfully redeemed {item_name} for {item['price']} {self.currency} on server {server}. You now have {new_points} {self.currency} left.",
            color=nextcord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @redeem.on_autocomplete("server")
    async def on_autocomplete_server(
        self, interaction: nextcord.Interaction, current: str
    ):
        choices = [
            server for server in self.servers if current.lower() in server.lower()
        ][:25]
        await interaction.response.send_autocomplete(choices)

    @redeem.on_autocomplete("item_name")
    async def on_autocomplete_shop_items(
        self, interaction: nextcord.Interaction, current: str
    ):
        choices = [name for name in self.shop_items if current.lower() in name.lower()][
            :25
        ]
        await interaction.response.send_autocomplete(choices)

def setup(bot):
    config_path = "config.json"
    with open(config_path) as config_file:
        config = json.load(config_file)

    economy_settings = config.get("ECONOMY_SETTINGS", {})
    if not economy_settings.get("enabled", False):
        return

    bot.add_cog(ShopCog(bot))
