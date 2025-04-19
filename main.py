import discord
import random
from discord import option
import ast
import asyncio
import requests
from html import unescape
from datetime import *

discord.MemberCacheFlags.all()

bot = discord.Bot(intents=discord.Intents.all())

f = open("save.txt", "r", encoding='utf-8')
global cache
c = f.read()
globals()['cache'] = [] if c == "" else ast.literal_eval(c)
print("Cache loaded: " + str(globals()['cache']))
f = open("questions.txt", "r", encoding='utf-8')
global questions
c = f.read()
globals()['questions'] = [] if c == "" else ast.literal_eval(c)

async def daily_code():
    if len(globals()['questions']['others']) <= 2:
        await fetch_new_questions()
    for g in globals()['cache']:
        if g['last_date'] != str(date.today()):
            await process_day(g,False)
    await save()
    response = requests.post("https://trivia.illusioncraft.net/input/?validation=[VALIDATION]&file=0", json=globals()['cache'])
    response2 = requests.post("https://trivia.illusioncraft.net/input/?validation=[VALIDATION]&file=1", json=globals()['questions'])

class DailyQuestion(discord.ui.View):
    def __init__(self,ans):
        super().__init__()
        self.answers = ans
        self.emojis = ["ð¦","ð§","ð¨","ð©","ðª"]
        self.add_buttons()
    def add_buttons(self):
        self.timeout = 86400
        for i in range(len(self.answers)):
            button = discord.ui.Button(label=self.answers[i],emoji=self.emojis[i],style=discord.ButtonStyle.green,custom_id=self.answers[i])
            async def button_example(interaction:discord.Interaction):
                self.disable_all_items()
                if interaction.message.id != await get_value(interaction.guild_id,"previous_poll"):
                    await interaction.response.send_message("That is not the current trivia question.",ephemeral=True)
                    return
                r = (await get_user_trivia_response(interaction.guild_id,interaction.user.id))
                if r != None:
                    r = r['val']
                if r == None:
                    await interaction.response.send_message("**" + interaction.custom_id + "** is now selected as your answer.",ephemeral=True)
                elif r == interaction.custom_id:
                    await interaction.response.send_message("**" + interaction.custom_id + "** was already selected as your answer. (And still is)",ephemeral=True)
                else:
                    await interaction.response.send_message("**" + interaction.custom_id + "** is now selected as your answer (Replacing your previous answer of **" + r + "**).",ephemeral=True)
                await set_user_trivia_response(interaction.guild_id,interaction.user.id,interaction.custom_id,interaction.user.name)
                await set_user_value(interaction.guild_id,interaction.user.id,"name",interaction.user.name)
                await save()
            button.callback = button_example
            self.add_item(button)

@bot.slash_command(name="leaderboard",description="Display a leaderboard")
@option("leaderboard",description="Leaderboard type",choices=["Correct","Incorrect","Percentage","Current Streak","Longest Streak","Total Questions Answered"])
async def leaderboard(ctx,leaderboard):
    embed = await new_embed()
    embed.description = "Leaderboard for `" + ctx.guild.name + "` (" + leaderboard + ")"
    us = await get_value(ctx.guild.id,"users")
    if leaderboard == "Correct":
        us.sort(key=sc)
    elif leaderboard == "Incorrect":
        us.sort(key=si)
    elif leaderboard == "Percentage":
        us.sort(key=sp)
    elif leaderboard == "Current Streak":
        us.sort(key=ss)
    elif leaderboard == "Longest Streak":
        us.sort(key=sl)
    elif leaderboard == "Total Questions Answered":
        us.sort(key=tq)
    for v in range(0,len(us)):
        if us[v]["name"] == "Unknown User":
            continue
        t = str(us[v]["correct"] if leaderboard == "Correct" else us[v]["incorrect"])
        t = str(us[v]["streak"]) if leaderboard == "Current Streak" else t
        t = str(us[v]["longest_streak"]) if leaderboard == "Longest Streak" else t
        t = str(us[v]["correct"] + us[v]["incorrect"]) if leaderboard == "Total Questions Answered" else t
        if leaderboard == "Percentage":
            t = str(round(us[v]["correct"] / (us[v]["correct"] + us[v]["incorrect"]) * 100,2)) + "%"
        embed.description += "\n**" + str(v + 1) + ".** " + us[v]["name"] + ": **" + t + "**"
    await ctx.respond(embed=embed)

def sc(a):
  return -(a["correct"])
def si(a):
  return -(a["incorrect"])
def ss(a):
  return -(a["streak"])
def sl(a):
  return -(a["longest_streak"])
def sp(a):
  if (a["name"] == "Unknown User"):
      return 0
  return -(a["correct"] / (a["correct"] + a["incorrect"]))
def tq(a):
  return -(a["correct"] + a["incorrect"])

async def process_day(d,isSilent):
    if d['channel'] == 0:
        return
    if not str(date.today()) in globals()['questions']:
        q = random.randint(0,len(globals()['questions']['others'])-1)
        globals()['questions'][str(date.today())] = globals()['questions']['others'][q]
        globals()['questions']['others'].pop(q)
        globals()['questions'][str(date.today())]['correct_answer'] = globals()['questions'][str(date.today())]['answers'][0]
        random.shuffle(globals()['questions'][str(date.today())]['answers'])
    channel = bot.get_channel(d['channel'])
    if channel is None:
        return
    if d['previous_poll'] != 0 and channel and d['last_date'] == str(date.today() - timedelta(days=1)):
        try:
            message = (await channel.fetch_message(d['previous_poll']))
            maxl = len(d['what_users_said'])
            gotit = 0
            correct_user_list = []
            correct_user_ids = []
            answer = globals()['questions'][str(date.today() - timedelta(days=1))]['correct_answer']
            letter = ["A","B","C","D","E"][globals()['questions'][str(date.today() - timedelta(days=1))]['answers'].index(answer)]
            dontclearstreak = []
            for u in d['what_users_said']:
                if d['what_users_said'][u]["val"] == answer:
                    gotit += 1
                    new_streak = await get_user_value(d['guild'],u,"streak") + 1
                    correct_user_list.append(" **" + str(d['what_users_said'][u]["name"]) + "**")
                    correct_user_ids.append(u)
                    await set_user_value(d['guild'],u,"correct",await get_user_value(d['guild'],u,"correct") + 1)
                    await set_user_value(d['guild'],u,"streak",new_streak)
                    await set_user_value(d['guild'],u,"longest_streak",max(new_streak,await get_user_value(d['guild'],u,"longest_streak")))
                    dontclearstreak.append(u)
                else:
                    await set_user_value(d['guild'],u,"incorrect",await get_user_value(d['guild'],u,"incorrect") + 1)
            for u in d['users']:
                if not u['user'] in dontclearstreak:
                    await set_user_value(d['guild'],u['user'],"streak",0)
            percent = gotit / maxl * 100 if maxl != 0 else 0
            percent = round(percent,2)
            gjt = "\nGood job to" + ",".join(correct_user_list) if len(correct_user_list) > 0 else ""
            msg = "The correct answer was " + letter + ": " + answer + "!\n**" + str(percent) + "%** got it! **(" + str(gotit) + "/" + str(maxl) + ")**" + gjt
            await set_value(d['guild'],"what_users_said",{})
            temp = await get_value(d['guild'],"previous_days")
            temp[str(date.today() - timedelta(days=1))] = {"correct":gotit,"total":maxl,"correct_users":correct_user_ids}
            await set_value(d['guild'],"previous_days",temp)
            embed = await new_embed()
            embed.description = msg
            await channel.send(embed=embed,reference=message)
        except Exception as e:
            print(str(e) + " 1")
    question_embed = await new_embed()
    question_embed.description = "**Daily Trivia Question for " + str(date.today()) + "**\n" + globals()['questions'][str(date.today())]['question'] + "\n-# Questions pulled from [this open trivia database.](https://opentdb.com/)"
    try:
        v = await channel.send(silent=isSilent,embed=question_embed, view=DailyQuestion(globals()['questions'][str(date.today())]['answers']))
        await set_value(d['guild'],'last_date',str(date.today()))
        await set_value(d['guild'],'previous_poll',v.id)
    except Exception as e:
        print(str(e) + " 2")

async def create_guild(g,a,b):
    dict = {}
    dict['guild'] = g
    dict['users'] = []
    dict['channel'] = 0
    dict['last_date'] = ""
    dict['previous_poll'] = 0
    dict['what_users_said'] = {}
    if a is not None:
        dict[a] = b
    globals()['cache'].append(dict)
    return dict

@bot.slash_command(name="setchannel",description="Set the trivia channel")
@option("channel",discord.TextChannel,description="The channel to set as the trivia channel",required=False,channel_types=[discord.ChannelType.text, discord.ChannelType.voice, discord.ChannelType.private, discord.ChannelType.group, discord.ChannelType.news, discord.ChannelType.news_thread, discord.ChannelType.public_thread, discord.ChannelType.private_thread, discord.ChannelType.stage_voice])
async def set_channel(ctx,channel):
    nchannel = channel if channel is not None else ctx.channel
    await set_value(ctx.guild.id,"channel",nchannel.id)
    embed = await new_embed()
    embed.description = "Trivia channel set to " + nchannel.mention
    await ctx.respond(embed=embed,ephemeral=True)
    for g in globals()['cache']:
        if g['guild'] == ctx.guild.id:
            await process_day(g,True)

@bot.slash_command(name="add-trivia",description="Add Trivia")
@option("question",str,description="Question",required=True)
@option("correct_answer",str,description="Correct Answer",required=True)
@option("answer1",str,description="Answer 1",required=True)
@option("answer2",str,description="Answer 2",required=True)
@option("answer3",str,description="Answer 3",required=True)
@option("answer4",str,description="Answer 4",required=True)
async def add_trivia(ctx,question,correct_answer,answer1,answer2,answer3,answer4):
    embed = await new_embed()
    dict = {}
    dict['question'] = question
    dict['answers'] = [correct_answer,answer1,answer2,answer3,answer4]
    if ctx.author.id != 715380010902356029:
        globals()['questions']['custom'].append(dict)
        embed.description = "Only Scott can do that."
        await ctx.respond(embed=embed,ephemeral=True)
        await save()
        return
    globals()['questions']['others'].append(dict)
    embed.description = "Added ð"
    await ctx.respond(embed=embed,ephemeral=True)
    await save()

async def fetch_new_questions():
    r = requests.get('https://opentdb.com/api.php?amount=50&type=multiple')
    j = r.json()
    l = []
    for i in j['results']:
        dict = {}
        dict['question'] = await cleanse(i['question'])
        dict['answers'] = [await cleanse(i['correct_answer']),await cleanse(i['incorrect_answers'][0]),await cleanse(i['incorrect_answers'][1]),await cleanse(i['incorrect_answers'][2])]
        l.append(dict)
    globals()['questions']['others'] += l
    return

async def cleanse(str):
    return unescape(str)

@bot.slash_command(name="user",description="Display info about a user")
@option("user",discord.User,description="The user",required=False)
async def user(ctx,user):
    embed = await new_embed()
    u = user if user is not None else ctx.author
    i = await get_user_value(ctx.guild.id,u.id,"incorrect")
    c = await get_user_value(ctx.guild.id,u.id,"correct")
    s = await get_user_value(ctx.guild.id,u.id,"streak")
    l = await get_user_value(ctx.guild.id,u.id,"longest_streak")
    try:
        p = round(c / (i + c) * 100,2)
    except Exception as e:
        p = None
    embed.description = "**User data for " + u.name + ":**\nCorrect: **" + str(c) + "**\nIncorrect: **" + str(i) + "**\nCurrent Streak: **" + str(s) + "**\nLongest Streak: **" + str(l) + "**\nPercentage: **" + str(p) + "%**"
    await ctx.respond(embed=embed)
    

@bot.user_command(name="User Data")
async def user_data(ctx, user: discord.User):
    embed = await new_embed()
    u = user
    i = await get_user_value(ctx.guild.id,u.id,"incorrect")
    c = await get_user_value(ctx.guild.id,u.id,"correct")
    s = await get_user_value(ctx.guild.id,u.id,"streak")
    l = await get_user_value(ctx.guild.id,u.id,"longest_streak")
    try:
        p = round(c / (i + c) * 100,2)
    except Exception as e:
        p = None
    embed.description = "**User data for " + u.name + ":**\nCorrect: **" + str(c) + "**\nIncorrect: **" + str(i) + "**\nCurrent Streak: **" + str(s) + "**\nLongest Streak: **" + str(l) + "**\nPercentage: **" + str(p) + "%**"
    await ctx.respond(embed=embed)

async def set_user_trivia_response(g,u,w,n):
    dict = await get_value(g,"what_users_said")
    dict[u] = {"val":w,"name":n}
    await set_value(g,"what_users_said",dict)

async def get_user_trivia_response(g,u):
    dict = await get_value(g,"what_users_said")
    return dict[u] if u in dict else None

async def create_user(g,u,a,b):
    dict = {}
    dict['user'] = u
    dict['correct'] = 0
    dict['incorrect'] = 0
    dict['streak'] = 0
    dict['longest_streak'] = 0
    dict['name'] = "Unknown User"
    if a is not None:
        dict[a] = b
    (await get_value(g,"users")).append(dict)
    return dict

async def get_value(g,a):
    for s in globals()['cache']:
        if s['guild'] == g:
            return s[a]
    new_guild = await create_guild(g,None,None)
    return new_guild[a]

async def toggle_boolean_value(g,a):
    for s in globals()['cache']:
        if s['guild'] == g:
            s[a] = False if s[a] else True
            return s[a]
    new_guild = await create_guild(g,None,None)
    v = await set_value(g,a,False if new_guild[a] else True)
    return v

async def get_entire_data(g):
    for s in globals()['cache']:
        if s['guild'] == g:
            return s
    new_guild = await create_guild(g,None,None)
    return new_guild

async def set_value(g,a,b):
    for s in globals()['cache']:
        if s['guild'] == g:
            s[a] = b
            return b
    new_guild = await create_guild(g,a,b)
    return b

async def new_embed():
    r = random.randint(0,255)
    g = random.randint(0,255)
    b = random.randint(0,255)
    embed = discord.Embed(
        description="",
        color=discord.Colour.from_rgb(r,g,b)
    )
    return embed

async def save():
    with open("save.txt", "w", encoding='utf-8') as file:
        v = str(globals()['cache'])
        file.write(v)
    with open("questions.txt", "w", encoding='utf-8') as file:
        v = str(globals()['questions'])
        file.write(v)

async def get_user_value(g,u,a):
    for s in globals()['cache']:
        if s['guild'] == g:
            for t in s['users']:
                if t['user'] == u:
                    return t[a]
            new_user = await create_user(g,u,None,None)
            return new_user[a]
    await create_guild(g,None,None)
    new_user = await create_user(g,u,None,None)
    return new_user[a]

async def set_user_value(g,u,a,b):
    for s in globals()['cache']:
        if s['guild'] == g:
            for t in s['users']:
                if t['user'] == u:
                    t[a] = b
                    return t[a]
            new_user = await create_user(g,u,a,b)
            return new_user[a]
    await create_guild(g,None,None)
    new_user = await create_user(g,u,a,b)
    return new_user[a]

async def execute_periodically():
    while True:
        await daily_code()
        now = datetime.now()
        midnight = datetime.combine(now.date() + timedelta(days=1), time.min)
        seconds_to_midnight = (midnight - now).total_seconds()
        await asyncio.sleep(seconds_to_midnight + 30)

@bot.listen()
async def on_ready():
    bot.loop.create_task(execute_periodically())
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="trivia games"))

bot.run("[TOKEN]")
