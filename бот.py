import discord
from discord import app_commands
from discord.ext import commands
# Словарь для хранения времени входа на смену: {user_id: datetime_object}


# Права доступа бота
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Нужно для кадрового аудита (слежки за ролями)

bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# КОНФИГУРАЦИЯ (ВСТАВЬ СВОИ ID КАНАЛОВ И РОЛЕЙ)
# ==========================================
CHANNEL_AUDIT_LOG_ID = 1555966245780717679    # Канал для логов кадрового аудита
CHANNEL_REPORTS_ID = 1555967728622239756      # Канал, куда будут приходить отчеты
CATEGORY_TICKETS_ID = 1556960255680847873    # Категория, где будут создаваться тикеты
ROLE_STAFF_ID = 1555971180236640347         # Роль руководства/персонала, имеющего доступ к тикетам
CHANNEL_MESSAGE_LOG_ID = 1556960335833862315  # ID канала для логов удаленных/измененных сообщений

active_shifts = {}
# ==========================================
# 1. СИСТЕМА ОТЧЕТОВ (MODAL + EMBED)
# ==========================================
class ReportModal(discord.ui.Modal, title="Подача официального отчета"):
    rank = discord.ui.TextInput(
        label="Ваша должность / Звание",
        placeholder="Например: Прокурор / Следователь ГСУ...",
        required=True
    )
    work_done = discord.ui.TextInput(
        label="Проделанная работа",
        style=discord.TextStyle.paragraph,
        placeholder="Опишите проведенные мероприятия, расследования или проверки...",
        required=True
    )
    links = discord.ui.TextInput(
        label="Ссылки на документы / Материалы",
        style=discord.TextStyle.paragraph,
        placeholder="Вставьте ссылки на Google Docs, ордера или реестры...",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        reports_channel = interaction.guild.get_channel(CHANNEL_REPORTS_ID)
        if not reports_channel:
            await interaction.response.send_message("Ошибка: канал отчетов не найден.", ephemeral=True)
            return

        embed = discord.Embed(title="📊 Новый официальный отчет", color=discord.Color.blue())
        embed.add_field(name="Сотрудник", value=interaction.user.mention, inline=True)
        embed.add_field(name="Должность/Звание", value=self.rank.value, inline=True)
        embed.add_field(name="Проделанная работа", value=self.work_done.value, inline=False)
        if self.links.value:
            embed.add_field(name="Документы / Доказательства", value=self.links.value, inline=False)
        embed.set_footer(text=f"ID пользователя: {interaction.user.id}")

        await reports_channel.send(embed=embed)
        await interaction.response.send_message("Ваш отчет успешно отправлен!", ephemeral=True)


class ReportView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Подать отчет", style=discord.ButtonStyle.primary, custom_id="report_button")
    async def open_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportModal())


# ==========================================
# 2. СИСТЕМА ТИКЕТОВ (TICKETS SYSTEM)
# ==========================================
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Закрыть обращение", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Обращение будет удалено через 5 секунд...")
        await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=5))
        await interaction.channel.delete()


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Создать обращение", style=discord.ButtonStyle.success, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = guild.get_channel(CATEGORY_TICKETS_ID)
        staff_role = guild.get_role(ROLE_STAFF_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel_name = f"тикет-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)

        embed = discord.Embed(
            title="Официальное обращение",
            description=f"Здравствуйте, {interaction.user.mention}! Изложите суть вашего вопроса или заявления. Ожидайте ответа уполномоченного сотрудника.",
            color=discord.Color.green()
        )
        await ticket_channel.send(embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"Ваше обращение создано: {ticket_channel.mention}", ephemeral=True)


# ==========================================
# 3. КАДРОВЫЙ АУДИТ (TRACK ROLE CHANGES)
# ==========================================
RANKS_HIERARCHY = {
    1556181528126689331: 1,  # Прокурор-стажер
    1556182264759459840: 1,  #sledak stazher
    1556182187580194846: 2,  #ml sledak
    1556181483998150768: 2,  # Окружной прокурор
    1556182153241301002: 3, #sledak
    1556181445440053318: 3,  # Областной Прокурор
    1556182119019978802: 4, #st sledak
    1556181102287265942: 4,  # Прокурор офиса генерального прокурора и/или прокурор спец.отдела при ОГП
    1556181284219260980: 4,
    1556181236693733416: 4,
    1556181157438169128: 4,
    1556182052037070858: 5, #sledak po osobych
    1556182003018104882: 6, #st sledak po osobych
    1556180854131400766: 7,  # Заместитель начальника спец. отдела при ОГП
    1556181032473202708: 7,
    1556180757498699878: 7,
    1556180964797845560: 7,
    1556180581979529267: 8,
    1556180368959213569: 8,
    1556180652192309418: 8,
    1556180457861681172: 8,  # Начальник специального отдела при ОГП
    1556180248851251200: 9,  # Заместитель генерального прокурора Украины
    1556180185680978031: 10,  # Первый заместитель генерального прокурора Украины
    1556180106169421874: 11,  # Генеральный прокурор Украины
}
REPRIMAND_ROLES = [
    1556228030425464892,  # Выговор 1/3
    1556228101027921940,  # Выговор 2/3
    1556228145919819826,  # Выговор 3/3
]

# 3. Специальные статусы (Увольнение и Отпуск)
ROLE_DISMISSED_ID = 1556228501449998408  # Роль "Уволен" / "Увольнение"
ROLE_VACATION_ID = 1556228738700546118   # Роль "В отпуске" / "Отпуск"

# 4. Награды и отличия (Список из 15 ID ролей)
AWARD_ROLES = [
    1556192746178478151,  # Награда 1
    1556192877044965376,  # Награда 2
    1556192974336168016,  # Награда 3
    1556193069429293117,  # Награда 4
    1556193781538230343,  # Награда 5
    1556194017274765332,  # Награда 6
    1556195922260664392,  # Награда 7
    1556196341678346250,  # Награда 8
    1556196513984675852,  # Награда 9
    1556196616048742400,  # Награда 10
    1556197076956745798,  # Награда 11
    1556197140806635520,  # Награда 12
    1556197404741468180,  # Награда 13
    1556197469413449829,  # Награда 14
    1556197545607299083,  # Награда 15
]

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.roles == after.roles:
        return

    audit_channel = after.guild.get_channel(CHANNEL_AUDIT_LOG_ID)
    if not audit_channel:
        return

    added_roles = [r for r in after.roles if r not in before.roles]
    removed_roles = [r for r in before.roles if r not in after.roles]

    if not added_roles and not removed_roles:
        return

    title = "🔄 Кадровые изменения"
    color = discord.Color.gold()

    # --- ПРИОРИТЕТ 1: Увольнение ---
    if any(r.id == ROLE_DISMISSED_ID for r in added_roles):
        title = "❌ Увольнение из органов прокуратуры"
        color = discord.Color.dark_red()

    # --- ПРИОРИТЕТ 2: Отпуск ---
    elif any(r.id == ROLE_VACATION_ID for r in added_roles):
        title = "🏖️ Предоставление официального отпуска"
        color = discord.Color.teal()
    elif any(r.id == ROLE_VACATION_ID for r in removed_roles):
        title = "💼 Возвращение из отпуска"
        color = discord.Color.blue()

    # --- ПРИОРИТЕТ 3: Выговоры ---
    elif any(r.id in REPRIMAND_ROLES for r in added_roles):
        title = "⚠️ Применение дисциплинарного взыскания (Выговор)"
        color = discord.Color.orange()
    elif any(r.id in REPRIMAND_ROLES for r in removed_roles):
        title = "✅ Снятие дисциплинарного взыскания (Выговор)"
        color = discord.Color.green()

    # --- ПРИОРИТЕТ 4: Награды ---
    elif any(r.id in AWARD_ROLES for r in added_roles):
        title = "🏅 Награждение государственным / ведомственным отличием"
        color = discord.Color.purple()

    # --- ПРИОРИТЕТ 5: Повышение / Понижение по иерархии ---
    else:
        old_ranks = [RANKS_HIERARCHY[r.id] for r in before.roles if r.id in RANKS_HIERARCHY]
        new_ranks = [RANKS_HIERARCHY[r.id] for r in after.roles if r.id in RANKS_HIERARCHY]

        old_max = max(old_ranks) if old_ranks else 0
        new_max = max(new_ranks) if new_ranks else 0

        if new_max > old_max:
            title = "🔼 Повышение в должности"
            color = discord.Color.green()
        elif new_max < old_max:
            title = "🔽 Понижение в должности"
            color = discord.Color.red()

    # Сборка карточки (Embed)
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Сотрудник", value=after.mention, inline=False)

    if added_roles:
        embed.add_field(name="Выданные роли / Отличия", value=", ".join([r.mention for r in added_roles]), inline=True)
    if removed_roles:
        embed.add_field(name="Снятые роли / Статусы", value=", ".join([r.mention for r in removed_roles]), inline=True)

    # Ищем ответственного в Audit Log
    async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
        if entry.target.id == after.id:
            embed.add_field(name="Исполнитель (Кто внес изменения)", value=entry.user.mention, inline=False)
            break

    await audit_channel.send(embed=embed)
    
    
# ==========================================
# EXTRA 1
# ==========================================
class InfoModal(discord.ui.Modal, title="Публикация информации"):
    channel_id_input = discord.ui.TextInput(
        label="1556003659840618588",
        placeholder="1556003659840618588",
        required=True
    )
    title_input = discord.ui.TextInput(
        label="Заголовок сообщения",
        placeholder="Например: Важное объявление",
        required=True
    )
    content_input = discord.ui.TextInput(
        label="Текст сообщения",
        style=discord.TextStyle.paragraph,
        placeholder="Напишите всю информацию здесь...",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Ищем канал по введенному ID
        try:
            channel_id = int(self.channel_id_input.value)
            target_channel = interaction.guild.get_channel(channel_id)
        except ValueError:
            await interaction.response.send_message("❌ Неверный формат ID канала!", ephemeral=True)
            return

        if not target_channel:
            await interaction.response.send_message("❌ Канал не найден на этом сервере!", ephemeral=True)
            return

        # Создаем красивую карточку
        embed = discord.Embed(
            title=self.title_input.value,
            description=self.content_input.value,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Официальное уведомление • {interaction.guild.name}")

        # Отправляем в нужный канал
        await target_channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Информация успешно опубликована в {target_channel.mention}!", ephemeral=True)
# ==========================================
# 3. УЧЕТ СМЕН (SHIFT TRACKER)
# ==========================================

# Память для хранения времени входа на смену
active_shifts = {}

class ShiftControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🟢 Заступить на смену", style=discord.ButtonStyle.success, custom_id="start_shift")
    async def start_shift(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in active_shifts:
            await interaction.response.send_message("❌ Вы уже находитесь на смене!", ephemeral=True)
            return

        active_shifts[user_id] = discord.utils.utcnow()
        await interaction.response.send_message("✅ Вы успешно заступили на смену. Удачной службы!", ephemeral=True)

    @discord.ui.button(label="🔴 Покинуть смену", style=discord.ButtonStyle.danger, custom_id="end_shift")
    async def end_shift(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id not in active_shifts:
            await interaction.response.send_message("❌ Вы сейчас не находитесь на смене!", ephemeral=True)
            return

        start_time = active_shifts.pop(user_id)
        end_time = discord.utils.utcnow()

        duration = end_time - start_time
        hours, remainder = divmod(int(duration.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)

        audit_channel = interaction.guild.get_channel(CHANNEL_AUDIT_LOG_ID)
        if audit_channel:
            embed = discord.Embed(title="⏱️ Итоги рабочей смены", color=discord.Color.blue())
            embed.add_field(name="Сотрудник", value=interaction.user.mention, inline=False)
            embed.add_field(name="Время начала", value=f"<t:{int(start_time.timestamp())}:F>", inline=True)
            embed.add_field(name="Время окончания", value=f"<t:{int(end_time.timestamp())}:F>", inline=True)
            embed.add_field(name="Отработано времени", value=f"**{hours} ч. {minutes} мин.**", inline=False)
            await audit_channel.send(embed=embed)
            await interaction.response.send_message(f"🛑 Смена окончена. Вы отработали: **{hours} ч. {minutes} мин.**", ephemeral=True)
        else:
            await interaction.response.send_message(f"🛑 Смена окончена. Вы отработали: **{hours} ч. {minutes} мин.**\n⚠️ *Канал аудита не найден.*", ephemeral=True)

# ==========================================
# 5. РЕЕСТР ДОКУМЕНТОВ И ОРДЕРОВ
# ==========================================
class DocumentModal(discord.ui.Modal, title="Реестр процессуальных документов"):
    rank = discord.ui.TextInput(
        label="Ваша должность / Звание",
        placeholder="Например: Прокурор ОГП / Окружной прокурор...",
        required=True
    )
    doc_type = discord.ui.TextInput(
        label="Тип документа / Ордера",
        placeholder="Например: Ордер AR-001 / Постановление / Иск...",
        required=True
    )
    articles = discord.ui.TextInput(
        label="Инкриминируемые статьи / Гражданский кодекс",
        placeholder="Например: Ст. 109 УК, Ст. 112 УК...",
        required=True
    )
    doc_link = discord.ui.TextInput(
        label="Ссылка на документ / Дело (Google Docs)",
        placeholder="https://docs.google.com/...",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Канал для реестра документов (используем тот же CHANNEL_REPORTS_ID или отдельный)
        audit_channel = interaction.guild.get_channel(CHANNEL_REPORTS_ID)
        
        if not audit_channel:
            await interaction.response.send_message("❌ Ошибка: канал реестра документов не найден!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📜 Процессуальный документ: {self.doc_type.value}",
            color=discord.Color.dark_gold()
        )
        embed.add_field(name="Прокурор / Заявитель", value=interaction.user.mention, inline=True)
        embed.add_field(name="Должность", value=self.rank.value, inline=True)
        embed.add_field(name="Статьи / Основания", value=f"```text\n{self.articles.value}\n```", inline=False)
        embed.add_field(name="Официальный материал", value=f"[Перейти к документу]({self.doc_link.value})", inline=False)
        
        embed.set_footer(text=f"Зафиксировано в реестре • ID: {interaction.user.id}")
        embed.timestamp = discord.utils.utcnow()

        await audit_channel.send(embed=embed)
        await interaction.response.send_message("✅ Документ успешно внесен в официальный реестр!", ephemeral=True)


class DocumentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚖️ Внести документ / Ордер", style=discord.ButtonStyle.primary, custom_id="add_document")
    async def open_doc_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DocumentModal())

# ==========================================
# 6. РАЗДЕЛЬНЫЕ ПАНЕЛИ: БАН, МУТ, РОЛИ
# ==========================================

# --- 1. БАН ---
class BanModal(discord.ui.Modal, title="Вынесение постановления о бане"):
    target_id = discord.ui.TextInput(label="ID пользователя", placeholder="Введите Discord ID...", required=True)
    reason = discord.ui.TextInput(label="Причина / Статья", placeholder="Укажите основание...", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        audit_channel = guild.get_channel(CHANNEL_AUDIT_LOG_ID)
        
        try:
            member = await guild.fetch_member(int(self.target_id.value.strip()))
            await guild.ban(member, reason=f"По требованию {interaction.user}: {self.reason.value}")
            
            embed = discord.Embed(title="🔨 Вынесено постановление о бане", color=discord.Color.dark_red())
            embed.add_field(name="Инициатор", value=interaction.user.mention, inline=True)
            embed.add_field(name="Нарушитель", value=member.mention, inline=True)
            embed.add_field(name="Причина", value=self.reason.value, inline=False)
            if audit_channel: await audit_channel.send(embed=embed)
            
            await interaction.followup.send(f"✅ Пользователь {member.mention} успешно заблокирован.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)

class BanView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔨 Заблокировать (Ban)", style=discord.ButtonStyle.danger, custom_id="btn_ban")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BanModal())


# --- 2. МУТ ---
class MuteModal(discord.ui.Modal, title="Вынесение постановления о муте"):
    target_id = discord.ui.TextInput(label="ID пользователя", placeholder="Введите Discord ID...", required=True)
    duration_input = discord.ui.TextInput(label="Срок мута", placeholder="Например: 30m, 2h, 1d", required=True)
    reason = discord.ui.TextInput(label="Причина / Статья", placeholder="Укажите основание...", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        audit_channel = guild.get_channel(CHANNEL_AUDIT_LOG_ID)
        
        try:
            member = await guild.fetch_member(int(self.target_id.value.strip()))
            time_str = self.duration_input.value.strip().lower()
            
            delta = datetime.timedelta(minutes=30)
            if time_str.endswith("m"): delta = datetime.timedelta(minutes=int(time_str[:-1]))
            elif time_str.endswith("h"): delta = datetime.timedelta(hours=int(time_str[:-1]))
            elif time_str.endswith("d"): delta = datetime.timedelta(days=int(time_str[:-1]))

            await member.timeout(delta, reason=self.reason.value)
            
            embed = discord.Embed(title="🔇 Вынесено постановление о муте", color=discord.Color.orange())
            embed.add_field(name="Инициатор", value=interaction.user.mention, inline=True)
            embed.add_field(name="Нарушитель", value=member.mention, inline=True)
            embed.add_field(name="Срок", value=time_str, inline=True)
            embed.add_field(name="Причина", value=self.reason.value, inline=False)
            if audit_channel: await audit_channel.send(embed=embed)
            
            await interaction.followup.send(f"✅ Пользователь {member.mention} заглушен на {time_str}.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)

class MuteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔇 Выдать мут (Timeout)", style=discord.ButtonStyle.secondary, custom_id="btn_mute")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MuteModal())


# --- 3. ИЗМЕНЕНИЕ РОЛЕЙ ---
class RolesModal(discord.ui.Modal, title="Кадровое изменение ролей"):
    target_id = discord.ui.TextInput(label="ID сотрудника", placeholder="Введите Discord ID...", required=True)
    roles_ids_input = discord.ui.TextInput(label="ID ролей (через пробел)", placeholder="111111 222222...", required=True)
    reason = discord.ui.TextInput(label="Основание / Приказ", placeholder="Укажите причину изменения...", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        audit_channel = guild.get_channel(CHANNEL_AUDIT_LOG_ID)
        
        try:
            member = await guild.fetch_member(int(self.target_id.value.strip()))
            role_ids = self.roles_ids_input.value.strip().split()
            added, removed = [], []

            for r_id in role_ids:
                role = guild.get_role(int(r_id))
                if role:
                    if role in member.roles:
                        await member.remove_roles(role)
                        removed.append(role.mention)
                    else:
                        await member.add_roles(role)
                        added.append(role.mention)

            embed = discord.Embed(title="🔄 Кадровое изменение ролей", color=discord.Color.blue())
            embed.add_field(name="Инициатор", value=interaction.user.mention, inline=True)
            embed.add_field(name="Сотрудник", value=member.mention, inline=True)
            if added: embed.add_field(name="Выданы роли", value=", ".join(added), inline=False)
            if removed: embed.add_field(name="Сняты роли", value=", ".join(removed), inline=False)
            embed.add_field(name="Основание", value=self.reason.value, inline=False)
            
            if audit_channel: await audit_channel.send(embed=embed)
            await interaction.followup.send(f"✅ Роли пользователя {member.mention} успешно обновлены.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)

class RolesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔄 Изменить роли", style=discord.ButtonStyle.primary, custom_id="btn_roles")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RolesModal())

# ==========================================
# 7. ЛОГИРОВАНИЕ УДАЛЕНИЙ И ИЗМЕНЕНИЙ СООБЩЕНИЙ
# ==========================================

@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    # Отправляем в отдельный канал для сообщений
    log_channel = message.guild.get_channel(CHANNEL_MESSAGE_LOG_ID)
    if not log_channel:
        return

    embed = discord.Embed(
        title="🗑️ Сообщение удалено",
        color=discord.Color.red(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Автор", value=message.author.mention, inline=True)
    embed.add_field(name="Канал", value=message.channel.mention, inline=True)
    
    content = message.content if message.content else "*[Текст отсутствовал / Вложение]*"
    if len(content) > 1024:
        content = content[:1021] + "..."
        
    embed.add_field(name="Удаленный текст", value=f"```{content}```", inline=False)
    embed.set_footer(text=f"ID автора: {message.author.id} • ID сообщения: {message.id}")

    await log_channel.send(embed=embed)


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.author.bot or not before.guild or before.content == after.content:
        return

    # Отправляем в тот же отдельный канал для сообщений
    log_channel = before.guild.get_channel(CHANNEL_MESSAGE_LOG_ID)
    if not log_channel:
        return

    embed = discord.Embed(
        title="✏️ Сообщение отредактировано",
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Автор", value=before.author.mention, inline=True)
    embed.add_field(name="Канал", value=before.channel.mention, inline=True)
    embed.add_field(name="Ссылка", value=f"[Перейти к сообщению]({after.jump_url})", inline=True)

    before_text = before.content if before.content else "*[Пусто]*"
    after_text = after.content if after.content else "*[Пусто]*"

    if len(before_text) > 512: before_text = before_text[:509] + "..."
    if len(after_text) > 512: after_text = after_text[:509] + "..."

    embed.add_field(name="До изменения", value=f"```{before_text}```", inline=False)
    embed.add_field(name="После изменения", value=f"```{after_text}```", inline=False)
    embed.set_footer(text=f"ID автора: {before.author.id}")

    await log_channel.send(embed=embed)

# ==========================================
# ИНИЦИАЛИЗАЦИЯ И КОМАНДЫ
# ==========================================

@bot.event
async def on_ready():
    print(f"Бот успешно запущен как {bot.user}")
    
    bot.add_view(DocumentView())
    bot.add_view(BanView())
    bot.add_view(MuteView())
    bot.add_view(RolesView())
    
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} команд.")
    except Exception as e:
        print(f"Ошибка синхронизации: {e}")



@bot.command()
@commands.has_permissions(administrator=True)
async def спавн_отчеты(ctx):
    """Вызывает панель отчетов с кнопкой"""
    embed = discord.Embed(
        title="📋 Подача отчетов",
        description="Нажмите на кнопку ниже, чтобы открыть форму и подать официальный отчет.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=ReportView())


@bot.command()
@commands.has_permissions(administrator=True)
async def спавн_тикеты(ctx):
    """Вызывает панель обращений с кнопкой"""
    embed = discord.Embed(
        title="📩 Прием обращений",
        description="Нажмите на кнопку ниже, чтобы создать приватный канал для связи с руководство/составом.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=TicketView())

@bot.command()
@commands.has_permissions(administrator=True)
async def спавн_смена(ctx):
    embed = discord.Embed(
        title="🛡️ Управление сменой",
        description="Нажмите **«Заступить на смену»** для начала учета времени.\nПо окончании нажмите **«Покинуть смену»**.",
        color=discord.Color.dark_blue()
    )
    await ctx.send(embed=embed, view=ShiftControlView())
    
@bot.command()
@commands.has_permissions(administrator=True)
async def написать(ctx):
    """Вызывает форму для публикации информации от лица бота"""
    try:
        await ctx.message.delete()
    except:
        pass
    
    # Создаем кнопку, по нажатию на которую откроется форма
    class OpenInfoModalView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)

        @discord.ui.button(label="📝 Написать объявление", style=discord.ButtonStyle.primary)
        async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(InfoModal())

    await ctx.send("Нажмите на кнопку ниже, чтобы открыть форму публикации:", view=OpenInfoModalView())

@bot.command()
@commands.has_permissions(administrator=True)
async def спавн_документы(ctx):
    """Вызывает панель регистрации процессуальных документов"""
    try:
        await ctx.message.delete()
    except:
        pass

    embed = discord.Embed(
        title="⚖️ Реестр процессуальных документов и ордеров",
        description="Нажмите на кнопку ниже, чтобы внести новый ордер, постановление или процессуальный документ в единую базу прокуратуры.",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed, view=DocumentView())
    
@bot.command()
@commands.has_permissions(administrator=True)
async def спавн_бан(ctx):
    """Вызывает панель блокировок"""
    try:
        await ctx.message.delete()
    except:
        pass
    embed = discord.Embed(
        title="🔨 Панель блокировок",
        description="Нажмите на кнопку ниже, чтобы вынести постановление о бане нарушителя.",
        color=discord.Color.dark_red()
    )
    await ctx.send(embed=embed, view=BanView())

@bot.command()
@commands.has_permissions(administrator=True)
async def спавн_мут(ctx):
    """Вызывает панель мутов (таймаутов)"""
    try:
        await ctx.message.delete()
    except:
        pass
    embed = discord.Embed(
        title="🔇 Панель временных ограничений (Мут)",
        description="Нажмите на кнопку ниже, чтобы заглушить пользователя.",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed, view=MuteView())

@bot.command()
@commands.has_permissions(administrator=True)
async def спавн_роли(ctx):
    """Вызывает панель изменения кадровых ролей"""
    try:
        await ctx.message.delete()
    except:
        pass
    embed = discord.Embed(
        title="🔄 Панель кадровых изменений",
        description="Нажмите на кнопку ниже, чтобы выдать или снять роли сотруднику.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=RolesView())
    
@bot.command()
@commands.has_permissions(administrator=True)
async def обновить_состав(ctx):
    """Сканирует сервер и выводит актуальный кадровый состав ОГП"""
    try:
        await ctx.message.delete()
    except:
        pass

    guild = ctx.guild
    
    # 🔥 ВПИШИ СЮДА СВОИ ID РОЛЕЙ ВМЕСТО НУЛЕЙ
    hierarchy = [
        (1556180106169421874, "ГЕНЕРАЛЬНЫЙ ПРОКУРОР"),
        (1556180185680978031, "ПЕРВЫЙ ЗАМЕСТИТЕЛЬ ГЕНЕРАЛЬНОГО ПРОКУРОРА"),
        
        (1556180652192309418, "НАЧАЛЬНИК ГСУ"),
        (1556181032473202708, "Заместитель начальника ГСУ"),
        
        (1556180581979529267, "НАЧАЛЬНИК ГИП"),
        (1556180964797845560, "Заместитель начальника ГИП"),
        
        (1556180368959213569, "НАЧАЛЬНИК УЧЕБКИ"),
        (1556180757498699878, "Заместитель начальника учебки"),
        
        (1556180457861681172, "НАЧАЛЬНИК ОТДЕЛА ПРиПБ"),
        (1556180854131400766, "Заместитель начальника отдела ПРиПБ"),
        
        (1556232030184808500, "ПРОКУРОР"),
        (1556181528126689331, "СТАЖЕР"),
        
        (1556172275198328893, "СЛЕДОВАТЕЛЬ"),
        (1556182264759459840, "СТАЖЕР ГСУ")
    ]

    embed = discord.Embed(
        title="📋 Кадровый состав Офиса Генерального прокурора",
        description="Официальный список руководства и сотрудников прокуратуры.",
        color=discord.Color.dark_blue(),
        timestamp=discord.utils.utcnow()
    )

    for role_id, title_name in hierarchy:
        role = guild.get_role(role_id)
        if not role:
            # Если роль еще не создана или ID неверный, пропускаем или пишем ошибку
            continue
        
        members_with_role = role.members
        
        if members_with_role:
            members_list = ", ".join([m.mention for m in members_with_role])
        else:
            members_list = "*Вакантно*"

        # Делаем оформление заголовков для красоты (руководству жирным/капсом)
        embed.add_field(name=f"📌 {title_name}", value=members_list, inline=False)

    embed.set_footer(text=f"Реестр кадров • {guild.name}")

    await ctx.send(embed=embed)
    
# Запуск бота
bot.run("MTU2NTY5MDU4NTU0NzgwODc3OA.GTc04v.TySvuLzpjtAZrqneA9335iHaviUV_EDiFAFFe4")