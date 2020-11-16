import os
import json
import discord
from discord.ext import commands
import datetime
import httplib2
from apiclient import discovery
from google.oauth2 import service_account
import random
import re
from pathlib import Path
import sys
import requests
from bs4 import BeautifulSoup

# -----------------------------------------
# Load bot
file_to_open = Path('config.json')
bot_data = []
if os.path.exists(file_to_open):
    with open(file_to_open) as json_file:
        bot_data = json.load(json_file)

bot = commands.Bot(command_prefix=bot_data['prefix'])
# -----------------------------------------
# Load spreadsheet 
# https://medium.com/@denisluiz/python-with-google-sheets-service-account-step-by-step-8f74c26ed28e

#edit the scopes if you want it to be readonly
scopes = ['https://www.googleapis.com/auth/spreadsheets']

#service account credentials
secret_file = Path('IdiotBotAuth.json')

credentials = service_account.Credentials.from_service_account_file(secret_file, scopes=scopes)
service = discovery.build('sheets', 'v4', credentials=credentials)

# The ID and range of the spreadsheet.
spreadsheet_id = bot_data['sheet']['sheetid']
spreadsheet_range_name = bot_data['sheet']['rangename']

# Call the Sheets API
sheet = service.spreadsheets()

# -----------------------------------------
#Util functions
# I just log by printing because heroku saves whatever is printed as logs
def log(message:str):
        print(str(datetime.datetime.now()) + ' - ' + message)

def log_command(ctx:commands.Context):
        log('User: ' + str(ctx.message.author.id) + ' Message: ' + ctx.message.content)

async def get_table():
    result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                range=spreadsheet_range_name).execute()
    values = result.get('values', [])

    if not values:
        log('No data found in the sheet.')
    else:
        # Resize rows to not bug on if checks
        for i in range(len(values)):
            if len(values[i]) < len(bot_data['sheet']['columns']):
                values[i] = values[i] + [''] * (len(bot_data['sheet']['columns']) - len(values[i]))

    return values

async def update_table(ctx:commands.Context, column_to_update:int, updated_value:str):
    values = await get_table()

    if values:
        found_user = False
        for row in values:
            # Update row
            if row[bot_data['sheet']['columns']['discordid']] == str(ctx.message.author.id):
                found_user = True
                row[column_to_update] = updated_value

                # Update sheet
                data = {
                    'values' : values 
                }
                service.spreadsheets().values().update(spreadsheetId=spreadsheet_id, body=data, range=spreadsheet_range_name, valueInputOption='USER_ENTERED').execute()
                
                # Return message to user
                await ctx.send(ctx.message.author.mention + ' ```css\n' + 
                'Attendance: [' + row[bot_data['sheet']['columns']['attendance']] + ']\n' + 
                'Main Job: [' + row[bot_data['sheet']['columns']['main']] + ']\n' + 
                'Alt Jobs: [' + row[bot_data['sheet']['columns']['altjobs']] + ']\n' + 
                'Note: ['+ row[bot_data['sheet']['columns']['notes']] + ']```')
                
                break
        
        if not found_user:
            await ctx.send('Couldn\'t find member with the ID '+ str(ctx.message.author.id) + ' in the attendance sheet.')
            log('Couldn\'t find member with the ID'+ str(ctx.message.author.id) + 'in the attendance sheet.')

# So our bot won't reply to other bots
def caller_is_bot(ctx:commands.Context):
    return caller_is_bot(ctx.message)

# Slight work around so that the funcion would work with the dad bot functionality
def caller_is_bot(message:discord.Message):
    bot_role_id = bot_data['roles']['botid']
    if bot_role_id in [role.id for role in message.author.roles]:
        return True
    return False

# Guild = Server
def caller_in_guild(ctx:commands.Context):
    return bot_data['guildid'] == ctx.message.guild.id

def caller_in_bot_spam_channel(ctx:commands.Context):
    return ctx.message.channel.id == bot_data['channels']['botspamchannelid']


def caller_in_discussion_channel(ctx:commands.Context):
    return ctx.message.channel.id == bot_data['channels']['discussionchannelid']

def caller_in_general_channels_category(message:discord.Message):
    return message.channel.category_id == bot_data['channels']['generalcategoryid']

def caller_is_bodi(ctx: commands.Context):
    return ctx.message.author.id == bot_data['shall']['shallid']

# For checks you don't want an exception thrown for, and want to just silently return
def invalid_call_without_error_message(ctx:commands.Context):
    return caller_is_bot(ctx) or not caller_in_guild(ctx)

# Generate log on all calls or meme messages for all calls
async def generic_functions_to_run_on_all_commands(ctx:commands.Context):
    log_command(ctx)

    if ctx.message.author.id == bot_data['shard']['shardid']:
        await ctx.send(pay_geitzz())

# Just a string generator to reduce copy paste
def pay_geitzz():
    return '<@' + str(bot_data['shard']['shardid']) + '> , you currently owe ' + str(bot_data['shard']['sharddebt']) + 'm to Geitzz. PAY YOUR DEBTS!'

# https://github.com/Vexs/DadBot
async def dadjoke(message:discord.Message):
    if not caller_is_bot(message) and caller_in_general_channels_category(message):
        match = re.search(r'\bi\'?\s*a?m\s+(.*)', message.content, re.IGNORECASE)
        if match is not None:
            word = match.group(1)
            if re.search(r'(Gryphon\s*Bot|620337281429012490)\s*', word, re.IGNORECASE):
                await message.channel.send('You\'re not GryphonBot, I\'m GryphonBot!')
            else:
                await message.channel.send('Hi {}, I\'m GryphonBot!'.format(word))

# -----------------------------------------
# Bot events
@bot.event
async def on_ready():
    if not bot_data['guildid'] in [guild.id for guild in bot.guilds]:
        return

    print(f'{bot.user} has connected to Discord! Connected to {len(bot.guilds)} guild(s).')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='Shard debt tracker: '+ str(bot_data['shard']['sharddebt']) + 'm'))

# Dad bot workaround
@bot.event
async def on_message(message:discord.Message):
    await dadjoke(message)
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx:commands.Context, error):
    log(f'Discord exception: "{error}" for message "{ctx.message.content}"\n')

    if isinstance(error, commands.CommandNotFound):
        await ctx.send('Command not found. Use !help for the list of commands.')

    elif isinstance(error, commands.DisabledCommand):
        await ctx.send(f'{ctx.command} has been disabled.')

    elif isinstance(error, commands.NoPrivateMessage):
            try:
                await ctx.author.send(f'{ctx.command} can not be used in Private Messages.')
            except discord.HTTPException:
                pass

    elif isinstance(error, commands.BadArgument):
        await ctx.send('Invalid argument(s). Use !help for the list of commands.')

    elif isinstance(error, commands.CheckFailure):
        await ctx.send('You do not have the correct role for this command.')
    
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send('This command is on cooldown, please retry in {}s.'.format(error.retry_after))
    
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send('You don\'t have the required permissions for this command.')

    elif isinstance(error, commands.UserInputError):
        await ctx.send('Invalid input. Use !help for the list of commands.')

    else: 
        await ctx.send(f'Unhandled discord exception: {error}\n')

# -----------------------------------------
# Bot commands

@bot.command(name='say', help= 'Makes the bot say something and delete your message. Admin only. Usage: ' + bot_data['prefix'] + 'say <what you want the bot to say>')
@commands.has_role(bot_data['roles']['adminid'])
@commands.guild_only()
async def say(ctx:commands.Context, *text:str):
    if invalid_call_without_error_message(ctx):
        return

    await generic_functions_to_run_on_all_commands(ctx)

    await ctx.send(' '.join(text))

    await ctx.message.delete()

@bot.command(name='pingatt', help= 'Ping members who didn\'t set attendance yet. Admin only. Usage: ' + bot_data['prefix'] + 'pingatt')
@commands.has_role(bot_data['roles']['adminid'])
@commands.guild_only()
async def pingatt(ctx:commands.Context):
    if invalid_call_without_error_message(ctx):
        return

    await generic_functions_to_run_on_all_commands(ctx)

    values = await get_table()
    pending = []
    for row in values:
        if row[bot_data['sheet']['columns']['attendance']] == '':
            if row[bot_data['sheet']['columns']['discordid']] != '':
                pending = pending + [row[bot_data['sheet']['columns']['discordid']]]
        
        # Feels kinda dirty, but I'm too lazy to change the rest of the code
        if row[bot_data['sheet']['columns']['main']] == 'Guest':
            break
        
    pings = ' '.join(map('<@{0}>'.format, pending))

    await ctx.send(pings + ', please set attendance for this week\'s WoE using the !setatt command.')

@bot.command(name='cleanatt', help= 'Clean WoE attendance. Can only be used by admins. Usage: ' + bot_data['prefix'] + 'cleanatt')
@commands.guild_only()
@commands.has_role(bot_data['roles']['adminid'])
async def cleanatt(ctx:commands.Context):
    if invalid_call_without_error_message(ctx):
        return

    await generic_functions_to_run_on_all_commands(ctx)

    values = await get_table()

    if values:
        for row in values:
            # Update row
            row[bot_data['sheet']['columns']['attendance']] = ''
            row[bot_data['sheet']['columns']['readstrat']] = ''

        # Update sheet
        data = {
            'values' : values 
        }
        service.spreadsheets().values().update(spreadsheetId=spreadsheet_id, body=data, range=spreadsheet_range_name, valueInputOption='USER_ENTERED').execute()

        await ctx.send('Attendance sheet cleared!')        

@bot.command(name='checkatt', help= 'Check confirmed WoE attendance. Can only be used on the #bot_spam channel. Usage: ' + bot_data['prefix'] + 'checkatt')
@commands.guild_only()
async def checkatt(ctx:commands.Context):
    if invalid_call_without_error_message(ctx):
        return

    if not caller_in_bot_spam_channel(ctx):
        await ctx.send('This command can only be used on the #bot_spam channel.')
        return

    await generic_functions_to_run_on_all_commands(ctx)

    values = await get_table()
    no = []
    yes = []
    for row in values:
        if row[bot_data['sheet']['columns']['attendance']] == 'Yes':
            yes = yes + [row[bot_data['sheet']['columns']['player']]]

        elif row[bot_data['sheet']['columns']['attendance']] == 'No':
            no = no + [row[bot_data['sheet']['columns']['player']]]

    await ctx.send('```css\n'+
    'Yes: [' + str(len(yes)) + ']\n' + 
    '\n'.join(yes) + '```')

    await ctx.send('```css\n'+
    'No: [' + str(len(no)) + ']\n' + 
    '\n'.join(no) + '```')

@bot.command(name='checkstrat', help= 'Checks who read the strats and updates the sheet. Can only be used by admins. Usage: ' + bot_data['prefix'] + 'checkstrat <strat message id>')
@commands.guild_only()
@commands.has_role(bot_data['roles']['adminid'])
async def checkstrat(ctx:commands.Context, msgid:int):
    if invalid_call_without_error_message(ctx):
        return

    await generic_functions_to_run_on_all_commands(ctx)

    values = await get_table()
    channel = bot.get_channel(bot_data['channels']['stratchannelid'])
    strat_message = await channel.fetch_message(msgid)
    readstrat = set()

    reactions = strat_message.reactions
    for reaction in reactions:
        users = await reaction.users().flatten()
        for user in users:
            readstrat.add(user.id)

    player_readstrat = []

    if values:
        for row in values:
            # Update row
            if row[bot_data['sheet']['columns']['attendance']] == 'Yes' and int(row[bot_data['sheet']['columns']['discordid']]) in readstrat:
                row[bot_data['sheet']['columns']['readstrat']] = 'OK'
                player_readstrat = player_readstrat + [row[bot_data['sheet']['columns']['player']]]

        # Update sheet
        data = {
            'values' : values 
        }
        service.spreadsheets().values().update(spreadsheetId=spreadsheet_id, body=data, range=spreadsheet_range_name, valueInputOption='USER_ENTERED').execute()

    await ctx.send('```css\n'+
    'Read strat: [' + str(len(player_readstrat)) + ']\n' + 
    '\n'.join(player_readstrat) + '```')

@bot.command(name='pingstrat', help= 'Checks who didn\'t read the strats and pings them. Can only be used by admins. Usage: ' + bot_data['prefix'] + 'pingstrat <strat message id>')
@commands.guild_only()
@commands.has_role(bot_data['roles']['adminid'])
async def pingstrat(ctx:commands.Context, msgid:int):
    if invalid_call_without_error_message(ctx):
        return

    await generic_functions_to_run_on_all_commands(ctx)

    await checkstrat(ctx, msgid)

    values = await get_table()
    player_didnt_readstrat = []

    if values:
        for row in values:
            # Update row
            if row[bot_data['sheet']['columns']['attendance']] == 'Yes' and row[bot_data['sheet']['columns']['readstrat']] == '':
                player_didnt_readstrat = player_didnt_readstrat + [row[bot_data['sheet']['columns']['discordid']]]

    pings = ' '.join(map('<@{0}>'.format, player_didnt_readstrat))
    await ctx.send(pings + ', go read this week\'s WoE strat!')

@bot.command(name='paygeitzz', help= 'Reminds shard to pay geitzz. Usage: ' + bot_data['prefix'] + 'paygeitzz')
@commands.guild_only()
async def paygeitzz(ctx:commands.Context):
    if invalid_call_without_error_message(ctx):
        return

    await generic_functions_to_run_on_all_commands(ctx)

    await ctx.send(pay_geitzz())

@bot.command(name='petgryphon', help= 'Pets the gryphon. Usage: ' + bot_data['prefix'] + 'petgryphon')
@commands.guild_only()
async def petgryphon(ctx:commands.Context):
    if invalid_call_without_error_message(ctx):
        return

    await generic_functions_to_run_on_all_commands(ctx)
    
    random_gryphon = random.randint(1, bot_data['maxgryphonpic'])

    file_to_open = os.path.join(os.getcwd(),'images/' + str(random_gryphon) + '.png')

    if os.path.exists(file_to_open):
        with open(file_to_open, 'rb') as file:
            picture = discord.File(file)
        await ctx.send(content='Thank you for the pets!', file=picture)

@bot.command(name='skarz', help= 'See the Skarz meme. Usage: ' + bot_data['prefix'] + 'skarz')
@commands.guild_only()
async def skarz(ctx:commands.Context):
    if invalid_call_without_error_message(ctx):
        return

    await generic_functions_to_run_on_all_commands(ctx)

    file_to_open = os.path.join(os.getcwd(),'images/skarz.png')

    if os.path.exists(file_to_open):
        with open(file_to_open, 'rb') as file:
            picture = discord.File(file)
        await ctx.send(file=picture)

@bot.command(name='von', help= 'See the Von meme. Usage: ' + bot_data['prefix'] + 'von')
@commands.guild_only()
async def von(ctx:commands.Context):
    if invalid_call_without_error_message(ctx):
        return

    await generic_functions_to_run_on_all_commands(ctx)

    file_to_open = os.path.join(os.getcwd(),'images/von.png')

    if os.path.exists(file_to_open):
        with open(file_to_open, 'rb') as file:
            picture = discord.File(file)
        await ctx.send(file=picture)

@bot.command(name='sig', help= 'Generate a NovaRO sig for your character. Usage: ' + bot_data['prefix'] + 'sig <character_name>')
@commands.guild_only()
async def sig(ctx:commands.Context, *character_name:str):
    if invalid_call_without_error_message(ctx):
        return

    await generic_functions_to_run_on_all_commands(ctx)

    bg = random.randint(1, 11)
    pose = random.randint(1, 13)

    await ctx.send('https://www.novaragnarok.com/ROChargenPHP/newsig/' + ' '.join(character_name).replace(' ', '%20')+ '/' + str(bg) + '/' + str(pose))

@bot.command(name='sig2', help= 'Generate a NovaRO sig for your character. Usage: ' + bot_data['prefix'] + 'sig "<character_name>" <bg id> <pose id>')
@commands.guild_only()
async def sig2(ctx:commands.Context, character_name:str, bg, pose):
    if invalid_call_without_error_message(ctx):
        return

    await generic_functions_to_run_on_all_commands(ctx)

    await ctx.send('https://www.novaragnarok.com/ROChargenPHP/newsig/' + character_name.replace(' ', '%20')+ '/' + str(bg) + '/' + str(pose))

@bot.command(name='setatt', help= 'Set WoE attendance. Can only be used on the #bot_spam channel. Usage: ' + bot_data['prefix'] + 'setatt <Yes/No>')
@commands.guild_only()
async def setatt(ctx:commands.Context, attendance:str):
    if invalid_call_without_error_message(ctx):
        return

    if not caller_in_bot_spam_channel(ctx):
         await ctx.send('This command can only be used on the #bot_spam channel.')
         return
         
    # Formats the submited text, ie. yes / Yes / yEs / YES => Yes
    attendance = attendance.title()

    await generic_functions_to_run_on_all_commands(ctx)

    if attendance not in ['Yes', 'No']:
        await ctx.send('You can only set your attendance to Yes or No.')
    else:
        await update_table(ctx, bot_data['sheet']['columns']['attendance'], attendance)

@bot.command(name='setmain', help= 'Set WoE main. Can only be used on the #bot_spam channel. Usage: ' + bot_data['prefix'] + 'setmain <main job>')
@commands.guild_only()
async def setmain(ctx:commands.Context, *main:str):
    if invalid_call_without_error_message(ctx):
        return

    if not caller_in_bot_spam_channel(ctx):
         await ctx.send('This command can only be used on the #bot_spam channel.')
         return
         
    await generic_functions_to_run_on_all_commands(ctx)

    await ctx.send('Changing your Main Job as requested. However, please don\'t use this command carelessly and without letting Shall know that you want to change, to avoid roster problems.')

    await update_table(ctx, bot_data['sheet']['columns']['main'], ' '.join(main))

@bot.command(name='setalts', help= 'Set WoE alts. Can only be used on the #bot_spam channel. Usage: ' + bot_data['prefix'] + 'setalts <alt job(s)>')
@commands.guild_only()
async def setalts(ctx:commands.Context, *alts:str):
    if invalid_call_without_error_message(ctx):
        return

    if not caller_in_bot_spam_channel(ctx):
         await ctx.send('This command can only be used on the #bot_spam channel.')
         return
         
    await generic_functions_to_run_on_all_commands(ctx)

    await update_table(ctx, bot_data['sheet']['columns']['altjobs'], ' '.join(alts))

@bot.command(name='setnote', help= 'Set a note. Can only be used on the #bot_spam channel. Usage: ' + bot_data['prefix'] + 'setnote <notes>')
@commands.guild_only()
async def setnote(ctx:commands.Context, *notes:str):
    if invalid_call_without_error_message(ctx):
        return

    if not caller_in_bot_spam_channel(ctx):
         await ctx.send('This command can only be used on the #bot_spam channel.')
         return
         
    await generic_functions_to_run_on_all_commands(ctx)

    await update_table(ctx, bot_data['sheet']['columns']['notes'], ' '.join(notes))
    
@bot.command(name='gvganalysis', help= 'Analyze the kills and deaths during WoE: ' + bot_data['prefix'] + 'gvganalysis <starttime> <endtime>')
@commands.guild_only()
async def gvganalysis(ctx:commands.Context, start:str, end:str):
    url_nova = "http://www.novaragnarok.com"
    url_woe = url_nova + "/?module=woe_stats"
    alliance = '3968'
    kills = dict()
    deaths = dict()
    start_time = start.split(':')
    end_time = end.split(':')
    
    await generic_functions_to_run_on_all_commands(ctx)
    
    if not caller_in_discussion_channel(ctx) and not caller_is_bodi(ctx):
        await ctx.send('You can only use this command on the discussion channel.')
        return

    try:
        start_minute = int(start_time[0])
        start_second = int(start_time[1])
        end_minute = int(end_time[0])
        end_second = int(end_time[1])
        
        if end_minute - start_minute > 3:
           await ctx.send('You can only analyze a maximum of 3 minutes.') 
           return
       
        if end_minute < start_minute or (end_minute == start_minute and start_minute > end_minute):
           await ctx.send('Invalid timestamps.')
           return
        
    except:
        await ctx.send('Invalid timestamps.')
        return
        
    try:
        message = await ctx.send('Please wait while I load the website. This process should take around 30s.') 
        # get the HTML from the page as pure text.
        woe = requests.get(url_woe)
        # Transforms the pure html text into a html object that can be filtered and searched properly.
        woe_html = BeautifulSoup(woe.text, "html.parser")
        # grab only the table I want from the whole page. The table is the list with all characters who played WoE. The list already includes all players, even if visually you can only see the 20 players per page in the website.
        woe_stats = woe_html.find(id="woe-stats")

        if woe_stats is not None:
            # for each row / player
            for row in woe_stats.findAll("tr"):
                cols = row.findAll("td")
                
                guild = cols[0].find('a').get('data-guild-id')
                name = cols[1].find('a').string.strip()
                url = cols[1].find('a')
                url_player = url_nova + url.get('href')
                

                    
                if guild == alliance:
                    # Open the player's page
                    user = requests.get(url_player)
                    user_html = BeautifulSoup(user.text, "html.parser")
                    # Get the rows in the player specific table
                    kills_table = user_html.find(id = "table-kills")
                    deaths_table = user_html.find(id = "table-deaths")
                    
                    
                    if kills_table is not None:                          
                        rows = kills_table.findAll("tr")
                        
                        for kill in rows:
                            cols = kill.findAll("td")
                            time = cols[5].string.strip().split(':')
                            victim = cols[2].find('a').string.strip()
                            skill = cols[4].string.strip()
                            time_minute = int(time[0])
                            time_second = int(time[1])           
                            
                            if time_minute > end_minute or (time_minute == end_minute and time_second > end_second):
                                break
                            
                            if time_minute < start_minute or (time_minute == start_minute and time_second < start_second):
                                continue
                            
                            if name not in kills:
                                kills[name] = dict()
                            
                            if skill not in kills[name]:
                                kills[name][skill] = []
                                
                            kills[name][skill].append(victim)
                            
                    if deaths_table is not None:                                             
                        rows = deaths_table.findAll("tr")
                        
                        for death in rows:
                            cols = death.findAll("td")
                            time = cols[5].string.strip().split(':')
                            killer = cols[2].find('a').string.strip()
                            skill = cols[4].string.strip()
                            time_minute = int(time[0])
                            time_second = int(time[1])           
                            
                            if time_minute > end_minute or (time_minute == end_minute and time_second > end_second):
                                break
                            
                            if time_minute < start_minute or (time_minute == start_minute and time_second < start_second):
                                continue
                            
                            if killer not in deaths:
                                deaths[killer] = dict()
                            
                            if skill not in deaths[killer]:
                                deaths[killer][skill] = []
                                
                            deaths[killer][skill].append(name)                    
        else:
            await ctx.send('Failed to load player table.')       
        
        report = ""
        
        report = report  + "KILLS ```"
        for killer in kills:
            for skill in kills[killer]:
                report = report  + killer + ' - ' + skill + ': ' + ', '.join(kills[killer][skill]) + '\n'
        report = report + '```'     
                
        report = report  + "DEATHS ```"
        for killer in deaths:
            for skill in deaths[killer]:
                report = report  + killer + ' - ' + skill + ': ' + ', '.join(deaths[killer][skill]) + '\n'
        report = report + '```'
                
        await message.edit(content = report)
                
    except:
        e = sys.exc_info()
        await ctx.send(e)

    
 
# -----------------------------------------
# Bot start
try:
    bot.run(bot_data['token'])
except:
    e = sys.exc_info()[0]
    print(e)
    log(f'Unhandled general exception: {e}\n')