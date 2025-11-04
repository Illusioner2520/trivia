import discord
import random
from discord import option
import ast
import asyncio
import requests
import sqlite3
from html import unescape
from datetime import *
import dateparser

discord.MemberCacheFlags.all()

bot = discord.Bot(intents=discord.Intents.all())

has_started = False

conn = sqlite3.connect("app.db", isolation_level=None)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, guild TEXT, user_id TEXT, attempted INTEGER, streak INTEGER, longest_streak INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS days (id INTEGER PRIMARY KEY, day TEXT, guild TEXT, question_id INTEGER, correct INTEGER, total INTEGER, question_order TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY, question TEXT, correct_answer TEXT, answer1 TEXT, answer2 TEXT, answer3 TEXT, source TEXT, used INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS correct (id INTEGER PRIMARY KEY, day TEXT, user_id TEXT, guild TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS guilds (id INTEGER PRIMARY KEY, guild TEXT, channel TEXT, previous_poll_id TEXT, last_date TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS guesses (id INTEGER PRIMARY KEY, guild TEXT, user TEXT, guess TEXT)")

class User:
    def __init__(self, id: str, name: str, guild: str):
        self.id = id
        cur.execute("SELECT * FROM users WHERE user_id = ? AND guild = ?", (id,guild))
        user = cur.fetchone()
        if not user and name:
            cur.execute("INSERT INTO users (name, guild, user_id, attempted, streak, longest_streak) VALUES (?,?,?,?,?,?)", (name,guild,id,0,0,0))
        if user and not user["name"] == name and name:
            cur.execute("UPDATE users SET name = ? WHERE guild = ? AND user_id = ?", (name,guild,id))
        attempted = user["attempted"] if user else 0
        self.name = user["name"] if user else name
        self.guild = guild
        cur.execute("SELECT * FROM correct WHERE user_id = ? AND guild = ?", (self.id, self.guild))
        correct = cur.fetchall()
        self.correct_list = correct
        self.correct = len(correct)
        self.total = attempted
        self.incorrect = attempted - self.correct
        self.percent = 0 if self.total == 0 else self.correct / self.total * 100
        self.streak = user["streak"] if user else 0
        self.longest_streak = user["longest_streak"] if user else 0
    def set_name(self, name: str):
        cur.execute("UPDATE users SET name = ? WHERE guild = ? AND user_id = ?", (name,self.guild,self.id))
        self.name = name
    def set_streak(self, streak: int):
        cur.execute("UPDATE users SET streak = ? WHERE guild = ? AND user_id = ?", (streak,self.guild,self.id))
        self.streak = streak
        if streak > self.longest_streak:
            self.set_longest_streak(streak)
    def set_longest_streak(self, longest_streak: int):
        cur.execute("UPDATE users SET longest_streak = ? WHERE guild = ? AND user_id = ?", (longest_streak,self.guild,self.id))
        self.longest_streak = longest_streak
    def get_correct_days(self):
        return list(map(lambda d: Day(d["day"], self.guild), self.correct_list))
    def increment_attempted(self):
        self.total += 1
        cur.execute("UPDATE users SET attempted = ? WHERE guild = ? AND user_id = ?", (self.total,self.guild,self.id))

class Day:
    def __init__(self, day_input: date, guild: str):
        self.day = day_input
        cur.execute("SELECT * FROM days WHERE day = ? AND guild = ?", (str(day_input),guild))
        day = cur.fetchone()
        question_id = -1
        order = ""
        added = False
        if not day and str(day_input) == str(date.today()):
            cur.execute("SELECT * FROM days WHERE day = ?", (str(day_input),))
            day1 = cur.fetchone()
            if not day1:
                question = Data.use_random_question()
                question_id = question.question_id
                order = ["1","2","3","c"]
                random.shuffle(order)
                order = ",".join(order)
            else:
                question_id = day1["question_id"]
                order = day1["question_order"]
            cur.execute("INSERT INTO days (day, guild, question_id, correct, total, question_order) VALUES (?,?,?,?,?,?)", (str(day_input), guild, question_id, 0, 0, order))
            added = True
        if (not added) and (not day):
            self.no = True
        else:
            self.no = False
        self.guild = guild
        self.question = Question(day["question_id"] if day else (question_id if question_id > 0 else 1))
        self.correct = day["correct"] if day else 0
        self.total = day["total"] if day else 0
        self.incorrect = self.total - self.correct
        self.order = day["question_order"] if day else order
    def get_correct_users(self):
        cur.execute("SELECT * FROM correct WHERE day = ? AND guild = ?", (str(self.day),self.guild))
        correct = cur.fetchall()
        return list(map(lambda u: User(u["user_id"], None, self.guild), correct))
    def set_correct(self, correct: int):
        cur.execute("UPDATE days SET correct = ? WHERE day = ? AND guild = ?", (correct, str(self.day), self.guild))
        self.correct = correct
        self.incorrect = self.total - self.correct
    def set_total(self, total: int):
        cur.execute("UPDATE days SET total = ? WHERE day = ? AND guild = ?", (total, str(self.day), self.guild))
        self.total = total
        self.incorrect = self.total - self.correct
    def set_correct_users(self, users):
        cur.execute("DELETE FROM correct WHERE day = ? AND guild = ?", (str(self.day), self.guild))
        for user in users:
            cur.execute("INSERT INTO correct (day, guild, user_id) VALUES (?,?,?)", (str(self.day), self.guild, user))
    
class Question:
    def __init__(self, question_id: int):
        self.question_id = question_id
        cur.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
        question = cur.fetchone()
        self.question = question["question"]
        self.correct_answer = question["correct_answer"]
        self.answer1 = question["answer1"]
        self.answer2 = question["answer2"]
        self.answer3 = question["answer3"]
        self.source = question["source"]
        self.used = bool(question["used"])
    def get_answers(self, order: str):
        order = order.split(",")
        answers = []
        for answer in order:
            if answer == "c":
                answers.append(self.correct_answer)
            elif answer == "1":
                answers.append(self.answer1)
            elif answer == "2":
                answers.append(self.answer2)
            elif answer == "3":
                answers.append(self.answer3)
        return answers


class Guild:
    def __init__(self, guild_input: str):
        self.guild = guild_input
        cur.execute("SELECT * FROM guilds WHERE guild = ?", (guild_input,))
        guild = cur.fetchone()
        if not guild:
            cur.execute("INSERT INTO guilds (guild, channel, previous_poll_id, last_date) VALUES (?,?,?,?)", (guild_input,0,0,0))
        self.channel = guild["channel"] if guild else 0
        self.previous_poll_id = guild["previous_poll_id"] if guild else 0
        self.last_date = guild["last_date"] if guild else 0
    def get_users(self):
        cur.execute("SELECT * FROM users WHERE guild = ?", (self.guild,))
        users = cur.fetchall()
        return list(map(lambda u: User(u["user_id"], u["name"], self.guild), users))
    def get_user(self, user_id: str, name: str):
        return User(user_id, name, self.guild)
    def get_day(self, day: date):
        return Day(day, self.guild)
    def set_channel(self, channel: str):
        cur.execute("UPDATE guilds SET channel = ? WHERE guild = ?", (channel, self.guild))
        self.channel = channel
    def set_previous_poll_id(self, previous_poll_id: str):
        cur.execute("UPDATE guilds SET previous_poll_id = ? WHERE guild = ?", (previous_poll_id, self.guild))
        self.previous_poll_id = previous_poll_id
    def set_last_date(self, last_date: date):
        cur.execute("UPDATE guilds SET last_date = ? WHERE guild = ?", (str(last_date), self.guild))
        self.last_date = str(last_date)
    def get_user_guess(self, user_id: str):
        cur.execute("SELECT * FROM guesses WHERE user = ? AND guild = ?", (user_id,self.guild))
        guess = cur.fetchone()
        if not guess:
            return None
        return guess["guess"]
    def get_user_guesses(self):
        cur.execute("SELECT * FROM guesses WHERE guild = ?", (self.guild,))
        guesses = cur.fetchall()
        return list(map(lambda g: Guess(self, g["user"], g["guess"]), guesses))
    def clear_user_guesses(self):
        cur.execute("DELETE FROM guesses WHERE guild = ?", (self.guild,))
    def set_user_guess(self, user_id: str, guess: str, name: str):
        user_id = str(user_id)
        user = User(user_id, name, self.guild)
        old_guess = self.get_user_guess(user_id)
        if old_guess == None:
            cur.execute("INSERT INTO guesses (user, guild, guess) VALUES (?,?,?)", (user_id, self.guild, guess))
        else:
            cur.execute("UPDATE guesses SET guess = ? WHERE user = ? AND guild = ?", (guess, user_id, self.guild))

class Guess:
    def __init__(self, guild: str, user: str, guess: str):
        self.guild = guild
        self.user = User(user, None, guild.guild)
        self.guess = guess

class Data:
    @staticmethod
    def get_questions():
        cur.execute("SELECT * FROM questions WHERE NOT used = ?", (int(True),))
        questions = cur.fetchall()
        return list(map(lambda q: Question(q["id"]), questions))
    
    @staticmethod
    def use_random_question():
        questions = Data.get_questions()
        if not questions:
            return None
        
        random_question = random.choice(questions)
        
        cur.execute("UPDATE questions SET used = ? WHERE id = ?", (int(True), random_question.question_id))
        return random_question

    @staticmethod
    def get_guilds():
        cur.execute("SELECT * FROM guilds")
        guilds = cur.fetchall()
        return list(map(lambda g: Guild(g["guild"]), guilds))
    
    @staticmethod
    def add_guild(guild: str, channel: str, poll_id: str, last_date: date):
        cur.execute("INSERT INTO guilds (guild, channel, previous_poll_id, last_date) VALUES (?,?,?)", (guild, channel, poll_id, str(last_date)))

    @staticmethod
    def add_question(question: str, correct_answer: str, answer1: str, answer2: str, answer3: str):
        cur.execute("INSERT INTO questions (question, correct_answer, answer1, answer2, answer3, source, used) VALUES (?,?,?,?,?,?,?)", (question, correct_answer, answer1, answer2, answer3, "custom", int(False)))

async def daily_code():
    if len(Data.get_questions()) <= 2:
        await fetch_new_questions()
    for guild in Data.get_guilds():
        if guild.last_date != str(date.today()):
            await process_day(guild,False)

class DailyQuestion(discord.ui.View):
    def __init__(self,ans):
        super().__init__()
        self.answers = ans
        self.emojis = ["🇦","🇧","🇨","🇩"]
        self.add_buttons()
    def add_buttons(self):
        self.timeout = 86400
        for i in range(len(self.answers)):
            button = discord.ui.Button(label=self.answers[i][:80],emoji=self.emojis[i],style=discord.ButtonStyle.green,custom_id=self.answers[i][:100])
            async def button_example(interaction:discord.Interaction):
                self.disable_all_items()
                guild = Guild(interaction.guild_id)
                if str(interaction.message.id) != guild.previous_poll_id:
                    await interaction.response.send_message("That is not the current trivia question.",ephemeral=True)
                    return
                old_user_guess = guild.get_user_guess(interaction.user.id)
                if old_user_guess == None:
                    await interaction.response.send_message("**" + interaction.custom_id + "** is now selected as your answer.",ephemeral=True)
                elif old_user_guess == interaction.custom_id:
                    await interaction.response.send_message("**" + interaction.custom_id + "** was already selected as your answer. (And still is)",ephemeral=True)
                else:
                    await interaction.response.send_message("**" + interaction.custom_id + "** is now selected as your answer (Replacing your previous answer of **" + old_user_guess + "**).",ephemeral=True)
                guild.set_user_guess(interaction.user.id, interaction.custom_id, interaction.user.name)
            button.callback = button_example
            self.add_item(button)

@bot.slash_command(name="leaderboard",description="Display a leaderboard")
@option("leaderboard",description="Leaderboard type",choices=["Correct","Incorrect","Percentage","Current Streak","Longest Streak","Total Questions Answered"])
@option("ephemeral",bool,description="Ephemeral",required=False)
async def leaderboard(ctx,leaderboard,ephemeral):
    if not ephemeral:
        ephemeral = False
    embed = await new_embed()
    embed.description = "Leaderboard for `" + ctx.guild.name + "` (" + leaderboard + ")"
    guild = Guild(ctx.guild.id)
    users = guild.get_users()
    if leaderboard == "Correct":
        users.sort(key=sc)
    elif leaderboard == "Incorrect":
        users.sort(key=si)
    elif leaderboard == "Percentage":
        users.sort(key=sp)
    elif leaderboard == "Current Streak":
        users.sort(key=ss)
    elif leaderboard == "Longest Streak":
        users.sort(key=sl)
    elif leaderboard == "Total Questions Answered":
        users.sort(key=tq)
    for v in range(0,len(users)):
        if users[v].name == "Unknown User":
            continue
        t = str(users[v].correct if leaderboard == "Correct" else users[v].incorrect)
        t = str(users[v].streak) if leaderboard == "Current Streak" else t
        t = str(users[v].longest_streak) if leaderboard == "Longest Streak" else t
        t = str(users[v].total) if leaderboard == "Total Questions Answered" else t
        if leaderboard == "Percentage":
            t = str(round(users[v].percent,2)) + "%"
        embed.description += "\n**" + str(v + 1) + ".** " + cleanse_username(users[v].name) + ": **" + t + "**"
    await ctx.respond(embed=embed,ephemeral=ephemeral)

def sc(a):
  return -(a.correct)
def si(a):
  return -(a.incorrect)
def ss(a):
  return -(a.streak)
def sl(a):
  return -(a.longest_streak)
def sp(a):
  return -(a.percent)
def tq(a):
  return -(a.total)

async def process_day(guild: Guild, isSilent):
    if guild.channel == 0:
        return
    today = Day(date.today(), guild.guild)
    today_question = today.question
    channel = bot.get_channel(int(guild.channel))
    if channel is None:
        return
    if guild.previous_poll_id != 0 and channel and guild.last_date == str(date.today() - timedelta(days=1)):
        try:
            message = (await channel.fetch_message(int(guild.previous_poll_id)))
            guesses = guild.get_user_guesses()
            day = Day(date.today() - timedelta(days=1), guild.guild)
            question = day.question
            total_guesses = len(guesses)
            correct_answers = 0
            correct_user_list = []
            correct_user_ids = []
            answer = question.correct_answer
            letter = ["A","B","C","D"][day.order.split(",").index("c")]
            dont_clear_streak = []
            for guess in guesses:
                guess.user.increment_attempted()
                if guess.guess == answer:
                    correct_answers += 1
                    new_streak = guess.user.streak + 1
                    correct_user_list.append("**" + cleanse_username(guess.user.name) + "**")
                    correct_user_ids.append(guess.user.id)
                    guess.user.set_streak(new_streak)
                    dont_clear_streak.append(guess.user.id)
            for user in guild.get_users():
                if not user.id in dont_clear_streak:
                    user.set_streak(0)
            percent = correct_answers / total_guesses * 100 if total_guesses != 0 else 0
            percent = round(percent,2)
            good_job_message = "\nGood job to " + ", ".join(correct_user_list) if len(correct_user_list) > 0 else ""
            msg = "The correct answer was " + letter + ": " + answer + "!\n**" + str(percent) + "%** got it! **(" + str(correct_answers) + "/" + str(total_guesses) + ")**" + good_job_message
            guild.clear_user_guesses()
            day.set_correct(correct_answers)
            day.set_total(total_guesses)
            day.set_correct_users(correct_user_ids)
            embed = await new_embed()
            embed.description = msg
            await channel.send(embed=embed,reference=message)
        except Exception as e:
            embed = await new_embed()
            embed.description = "There was an error when creating embed: " + str(e)
            await channel.send(silent=True,embed=embed)
    question_embed = await new_embed()
    question_embed.description = "**Daily Trivia Question for " + str(date.today()) + "**\n" + today_question.question + "\n-# Questions pulled from [this open trivia database.](https://opentdb.com/)"
    try:
        v = await channel.send(silent=isSilent,embed=question_embed, view=DailyQuestion(today_question.get_answers(today.order)))
        await v.create_thread(name=str(date.today()) + " Trivia Question", auto_archive_duration=1440)
        guild.set_last_date(date.today())
        guild.set_previous_poll_id(v.id)
    except Exception as e:
        embed = await new_embed()
        embed.description = "There was an error when creating embed: " + str(e)
        await channel.send(silent=True,embed=embed)

@bot.slash_command(name="setchannel",description="Set the trivia channel")
@option("channel",discord.TextChannel,description="The channel to set as the trivia channel",required=False,channel_types=[discord.ChannelType.text, discord.ChannelType.voice, discord.ChannelType.private, discord.ChannelType.group, discord.ChannelType.news, discord.ChannelType.news_thread, discord.ChannelType.public_thread, discord.ChannelType.private_thread, discord.ChannelType.stage_voice])
async def set_channel(ctx,channel):
    nchannel = channel if channel is not None else ctx.channel
    guild = Guild(ctx.guild.id)
    guild.set_channel(nchannel.id)
    embed = await new_embed()
    embed.description = "Trivia channel set to " + nchannel.mention
    await ctx.respond(embed=embed,ephemeral=True)
    await process_day(guild, True)

@bot.slash_command(name="debug",description="Debug")
@option("type",description="Debug type",choices=["Guesses"])
async def debug(ctx,type):
    embed = await new_embed()
    if ctx.author.id != 715380010902356029:
        embed.description = "Only Scott can do that."
        await ctx.respond(embed=embed,ephemeral=True)
        return
    guild = Guild(ctx.guild.id)
    guesses = guild.get_user_guesses()
    if type == "Guesses":
        embed.description = "**Today's Guesses**\n" + "\n".join(list(map(lambda g: cleanse_username(g.user.name) + ": **" + g.guess + "**", guesses)))
        await ctx.respond(embed=embed,ephemeral=True)
        return

@bot.slash_command(name="add-trivia",description="Add Trivia")
@option("question",str,description="Question",required=True)
@option("correct_answer",str,description="Correct Answer",required=True)
@option("answer1",str,description="Answer 1",required=True)
@option("answer2",str,description="Answer 2",required=True)
@option("answer3",str,description="Answer 3",required=True)
async def add_trivia(ctx,question,correct_answer,answer1,answer2,answer3):
    embed = await new_embed()
    if ctx.author.id != 715380010902356029:
        embed.description = "Only Scott can do that."
        await ctx.respond(embed=embed,ephemeral=True)
        return
    Data.add_question(question, correct_answer, answer1, answer2, answer3)
    embed.description = "Added 👍"
    await ctx.respond(embed=embed,ephemeral=True)

async def fetch_new_questions():
    r = requests.get('https://opentdb.com/api.php?amount=50&type=multiple')
    j = r.json()
    for i in j['results']:
        question = await cleanse(i['question'])
        correct_answer = await cleanse(i['correct_answer'])
        answer1 = await cleanse(i['incorrect_answers'][0])
        answer2 = await cleanse(i['incorrect_answers'][1])
        answer3 = await cleanse(i['incorrect_answers'][2])
        cur.execute("SELECT * FROM questions WHERE question = ?", (question,))
        already_exists = cur.fetchone()
        if already_exists:
            continue
        cur.execute("INSERT INTO questions (question, correct_answer, answer1, answer2, answer3, source, used) VALUES (?,?,?,?,?,?,?)", (question, correct_answer, answer1, answer2, answer3, "opentdb", int(False)))

async def cleanse(str):
    return unescape(str)

def cleanse_username(str: str):
    return str.replace("_", "\\_").replace("*", "\\*")

@bot.slash_command(name="day",description="Display info about a day")
@option("day",str,description="The day",required=True)
@option("ephemeral",bool,description="Ephemeral",required=False)
async def user(ctx,day,ephemeral):
    if not ephemeral:
        ephemeral = False
    datetime = dateparser.parse(day)
    embed = await new_embed()
    if not datetime:
        embed.description = "Invalid Date"
        await ctx.respond(embed=embed,ephemeral=True)
        return
    date_input = datetime.date()
    if (str(date_input) == str(date.today())):
        embed.description = "You cannot view today's question yet"
        await ctx.respond(embed=embed,ephemeral=True)
        return
    day_obj = Day(date_input, ctx.guild.id)
    if day_obj.no:
        embed.description = "There wasn't a question asked on that day (" + str(date_input) + ")"
        await ctx.respond(embed=embed,ephemeral=True)
        return
    question = day_obj.question
    answers = question.get_answers(day_obj.order)
    total = day_obj.total
    percent = round(day_obj.correct / total * 100,2) if total > 0 else 0
    embed.description = "**Day data for " + str(date_input) + ":**\nQuestion: **" + question.question + "**\n\nAnswers:\n-A. **" + answers[0] + "**\n-B. **" + answers[1] + "**\n-C. **" + answers[2] + "**\n-D. **" + answers[3] + "**\n\nCorrect Answer: **" + question.correct_answer + "**\n**" + str(percent) + "%** got it! **(" + str(day_obj.correct) + "/" + str(total) + ")**\nThe following users got it right: " + ", ".join(list(map(lambda u: "**" + cleanse_username(u.name) + "**", day_obj.get_correct_users())))
    await ctx.respond(embed=embed,ephemeral=ephemeral)

@bot.slash_command(name="user",description="Display info about a user")
@option("user",discord.User,description="The user",required=False)
@option("ephemeral",bool,description="Ephemeral",required=False)
async def user(ctx,user,ephemeral):
    if not ephemeral:
        ephemeral = False
    embed = await new_embed()
    discord_user = user if user is not None else ctx.author
    user_obj = User(discord_user.id, discord_user.name, ctx.guild.id)
    incorrect = user_obj.incorrect
    correct = user_obj.correct
    streak = user_obj.streak
    longest_streak = user_obj.longest_streak
    percent = round(user_obj.percent,2)
    embed.description = "**User data for " + cleanse_username(user_obj.name) + ":**\nCorrect: **" + str(correct) + "**\nIncorrect: **" + str(incorrect) + "**\nCurrent Streak: **" + str(streak) + "**\nLongest Streak: **" + str(longest_streak) + "**\nPercentage: **" + str(percent) + "%**"
    await ctx.respond(embed=embed, ephemeral=ephemeral)
    

@bot.user_command(name="User Data")
async def user_data(ctx, user: discord.User):
    embed = await new_embed()
    discord_user = user
    user_obj = User(discord_user.id, discord_user.name, ctx.guild.id)
    incorrect = user_obj.incorrect
    correct = user_obj.correct
    streak = user_obj.streak
    longest_streak = user_obj.longest_streak
    percent = round(user_obj.percent,2)
    embed.description = "**User data for " + cleanse_username(user_obj.name) + ":**\nCorrect: **" + str(correct) + "**\nIncorrect: **" + str(incorrect) + "**\nCurrent Streak: **" + str(streak) + "**\nLongest Streak: **" + str(longest_streak) + "**\nPercentage: **" + str(percent) + "%**"
    await ctx.respond(embed=embed)

async def new_embed():
    r = random.randint(0,255)
    g = random.randint(0,255)
    b = random.randint(0,255)
    embed = discord.Embed(
        description="",
        color=discord.Colour.from_rgb(r,g,b)
    )
    return embed

async def execute_periodically():
    while True:
        await daily_code()
        now = datetime.now()
        midnight = datetime.combine(now.date() + timedelta(days=1), time.min)
        seconds_to_midnight = (midnight - now).total_seconds()
        await asyncio.sleep(seconds_to_midnight + 30)

@bot.listen()
async def on_ready():
    global has_started
    if not has_started:
        has_started = True
        bot.loop.create_task(execute_periodically())
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="trivia"))

bot.run("[TOKEN]")
