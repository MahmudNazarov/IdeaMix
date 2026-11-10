"""Idempotently populate IdeaMix with realistic demonstration data."""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from apps.models import (
    Category,
    Comment,
    Favorite,
    Idea,
    IdeaLike,
    Project,
    ProjectMember,
    UserProfile,
)

DEMO_CATEGORIES = [
    (
        'Технологии',
        'technology',
        'bi-cpu',
        'Разработка, инфраструктура и цифровые продукты.',
    ),
    (
        'ИИ и машинное обучение',
        'ai-ml',
        'bi-robot',
        'Интеллектуальные сервисы, анализ данных и автоматизация.',
    ),
    (
        'Бизнес',
        'business',
        'bi-briefcase',
        'Продукты для предпринимателей, команд и клиентов.',
    ),
    (
        'Образование',
        'education',
        'bi-mortarboard',
        'Обучение, наставничество и учебные инструменты.',
    ),
    (
        'Дизайн',
        'design',
        'bi-palette',
        'Интерфейсы, визуальные системы и творческие инструменты.',
    ),
    (
        'Здоровье',
        'health',
        'bi-heart-pulse',
        'Забота о физическом и эмоциональном благополучии.',
    ),
    (
        'Экология',
        'environment',
        'bi-tree',
        'Устойчивое развитие, переработка и забота о природе.',
    ),
    (
        'Продуктивность',
        'productivity',
        'bi-check2-square',
        'Планирование, привычки и организация времени.',
    ),
    (
        'Игры',
        'gaming',
        'bi-controller',
        'Игровые механики, симуляторы и сообщества игроков.',
    ),
    (
        'Сообщество',
        'community',
        'bi-people',
        'Локальные инициативы, взаимопомощь и совместные проекты.',
    ),
]

DEMO_USERS = [
    {
        'username': 'demo_alexey',
        'first_name': 'Алексей',
        'last_name': 'Морозов',
        'email': 'demo_alexey@ideamix.local',
        'bio': 'Продуктовый разработчик. Люблю превращать сложные задачи в простые сервисы.',
        'location': 'Ташкент',
        'skills': 'Python, Django, PostgreSQL, Docker',
    },
    {
        'username': 'demo_maria',
        'first_name': 'Мария',
        'last_name': 'Соколова',
        'email': 'demo_maria@ideamix.local',
        'bio': 'Исследовательница пользовательского опыта и наставница начинающих дизайнеров.',
        'location': 'Москва',
        'skills': 'UX-исследования, интервью, прототипирование, Figma',
    },
    {
        'username': 'demo_ivan',
        'first_name': 'Иван',
        'last_name': 'Петров',
        'email': 'demo_ivan@ideamix.local',
        'bio': 'Backend-разработчик, интересуюсь системами рекомендаций и обработкой данных.',
        'location': 'Санкт-Петербург',
        'skills': 'Python, FastAPI, Redis, SQL',
    },
    {
        'username': 'demo_elena',
        'first_name': 'Елена',
        'last_name': 'Кузнецова',
        'email': 'demo_elena@ideamix.local',
        'bio': 'Методист образовательных программ и автор интерактивных курсов.',
        'location': 'Казань',
        'skills': 'Методика обучения, сценарии курсов, фасилитация',
    },
    {
        'username': 'demo_rustam',
        'first_name': 'Рустам',
        'last_name': 'Каримов',
        'email': 'demo_rustam@ideamix.local',
        'bio': 'Предприниматель и ментор стартапов на ранней стадии.',
        'location': 'Самарканд',
        'skills': 'Стратегия, финансы, переговоры, запуск продуктов',
    },
    {
        'username': 'demo_olga',
        'first_name': 'Ольга',
        'last_name': 'Лебедева',
        'email': 'demo_olga@ideamix.local',
        'bio': 'Дизайнер интерфейсов. Верю, что хороший дизайн начинается с внимания к людям.',
        'location': 'Новосибирск',
        'skills': 'UI-дизайн, дизайн-системы, доступность, Figma',
    },
    {
        'username': 'demo_dmitry',
        'first_name': 'Дмитрий',
        'last_name': 'Волков',
        'email': 'demo_dmitry@ideamix.local',
        'bio': 'Аналитик данных и автор небольших открытых библиотек.',
        'location': 'Екатеринбург',
        'skills': 'Python, Pandas, визуализация данных, статистика',
    },
    {
        'username': 'demo_anastasia',
        'first_name': 'Анастасия',
        'last_name': 'Павлова',
        'email': 'demo_anastasia@ideamix.local',
        'bio': 'Эколог и организатор городских сообществ. Развиваю культуру осознанного потребления.',
        'location': 'Москва',
        'skills': 'Экопроекты, работа с сообществами, события',
    },
    {
        'username': 'demo_timur',
        'first_name': 'Тимур',
        'last_name': 'Ахмедов',
        'email': 'demo_timur@ideamix.local',
        'bio': 'Мобильный разработчик, увлекаюсь городским транспортом и картами.',
        'location': 'Ташкент',
        'skills': 'Kotlin, Swift, карты, геоданные',
    },
    {
        'username': 'demo_irina',
        'first_name': 'Ирина',
        'last_name': 'Новикова',
        'email': 'demo_irina@ideamix.local',
        'bio': 'Врач и исследовательница цифровых инструментов для профилактики здоровья.',
        'location': 'Алматы',
        'skills': 'Медицина, клинические исследования, здоровый образ жизни',
    },
    {
        'username': 'demo_sergey',
        'first_name': 'Сергей',
        'last_name': 'Фёдоров',
        'email': 'demo_sergey@ideamix.local',
        'bio': 'Fullstack-разработчик. Собираю быстрые прототипы и проверяю гипотезы.',
        'location': 'Нижний Новгород',
        'skills': 'TypeScript, React, Node.js, Django',
    },
    {
        'username': 'demo_yulia',
        'first_name': 'Юлия',
        'last_name': 'Орлова',
        'email': 'demo_yulia@ideamix.local',
        'bio': 'Маркетолог и автор текстов о технологиях, людях и полезных продуктах.',
        'location': 'Бухара',
        'skills': 'Контент, маркетинг, бренд, коммуникации',
    },
    {
        'username': 'demo_bekzod',
        'first_name': 'Бекзод',
        'last_name': 'Рахимов',
        'email': 'demo_bekzod@ideamix.local',
        'bio': 'Инженер машинного обучения. Работаю с рекомендательными системами.',
        'location': 'Ташкент',
        'skills': 'ML, PyTorch, NLP, MLOps',
    },
    {
        'username': 'demo_natalia',
        'first_name': 'Наталья',
        'last_name': 'Зайцева',
        'email': 'demo_natalia@ideamix.local',
        'bio': 'Продюсер образовательных проектов и организатор менторских программ.',
        'location': 'Москва',
        'skills': 'Продюсирование, менторство, события, партнёрства',
    },
    {
        'username': 'demo_artem',
        'first_name': 'Артём',
        'last_name': 'Гусев',
        'email': 'demo_artem@ideamix.local',
        'bio': 'Геймдизайнер и разработчик небольших инди-игр.',
        'location': 'Санкт-Петербург',
        'skills': 'Unity, геймдизайн, C#, level-дизайн',
    },
]

# (title, category slug, status, visibility, tags, short description, full description)
DEMO_IDEAS = [
    (
        'Платформа обмена навыками «Умею»',
        'community',
        Idea.PUBLISHED,
        Idea.PUBLIC,
        'обмен навыками, менторство, сообщество',
        'Сервис, где люди обмениваются уроками вместо денег.',
        'Пользователь предлагает навык, который умеет хорошо, и получает взамен '
        'занятие по другому направлению. Внутри есть рейтинг, календарь встреч '
        'и безопасные онлайн-комнаты для занятий.',
    ),
    (
        'Нейросеть для проверки домашних заданий',
        'ai-ml',
        Idea.IN_PROGRESS,
        Idea.PUBLIC,
        'ИИ, образование, автоматизация',
        'Помощник учителя, который проверяет типовые задания и объясняет ошибки.',
        'Модель анализирует письменные ответы учеников, выделяет типичные ошибки '
        'и формирует короткие рекомендации. Учитель всегда принимает финальное '
        'решение, а ученик видит понятное объяснение.',
    ),
    (
        'Карта раздельного сбора отходов',
        'environment',
        Idea.PUBLISHED,
        Idea.PUBLIC,
        'экология, переработка, карта',
        'Городская карта пунктов приёма вторсырья с актуальными условиями.',
        'Сервис показывает ближайшие пункты приёма пластика, стекла и бумаги, '
        'часы работы и требования к сортировке. Пользователи могут подтверждать '
        'актуальность данных и добавлять новые точки.',
    ),
    (
        'Помощник семейного бюджета',
        'business',
        Idea.COMPLETED,
        Idea.PUBLIC,
        'финансы, бюджет, семья',
        'Простой планировщик расходов для семьи без сложных таблиц.',
        'Приложение помогает распределять доходы по конвертам, напоминает о '
        'регулярных платежах и показывает, как меняются накопления за месяц. '
        'Все расчёты сопровождаются понятными подсказками.',
    ),
    (
        'Курс финансовой грамотности для школьников',
        'education',
        Idea.DRAFT,
        Idea.PUBLIC,
        'финансы, школа, курс',
        'Интерактивный курс о деньгах, выборе и личных целях.',
        'Программа рассчитана на учеников старших классов и включает короткие '
        'уроки, практические задания и разбор реальных ситуаций. Материалы '
        'готовятся вместе с учителями и родителями.',
    ),
    (
        'Маркетплейс локальных мастеров',
        'business',
        Idea.PUBLISHED,
        Idea.PUBLIC,
        'маркетплейс, услуги, локальный бизнес',
        'Площадка, где можно найти проверенного мастера рядом с домом.',
        'Сервис объединяет небольшие мастерские и частных специалистов: '
        'ремонт, пошив, мебель и другие услуги. Карточки содержат портфолио, '
        'отзывы и понятные цены.',
    ),
    (
        'Тренажёр осознанного дыхания',
        'health',
        Idea.IN_PROGRESS,
        Idea.PUBLIC,
        'здоровье, дыхание, стресс',
        'Короткие дыхательные практики для снижения напряжения в течение дня.',
        'Приложение предлагает упражнения на две, пять и десять минут, '
        'подстраивается под самочувствие пользователя и напоминает о перерывах. '
        'Все рекомендации носят ознакомительный характер.',
    ),
    (
        'Генератор дизайн-систем для стартапов',
        'design',
        Idea.PUBLISHED,
        Idea.PUBLIC,
        'дизайн-система, UI, стартап',
        'Инструмент, который собирает базовую дизайн-систему из бренд-цветов.',
        'Сервис помогает небольшой команде быстро получить набор компонентов, '
        'токенов и правил типографики. Результат можно выгрузить в Figma или '
        'использовать как основу для собственной библиотеки.',
    ),
    (
        'Симулятор городского транспорта',
        'gaming',
        Idea.DRAFT,
        Idea.PUBLIC,
        'игры, транспорт, симулятор',
        'Игра о планировании маршрутов и управлении небольшим городом.',
        'Игрок развивает транспортную сеть, балансирует бюджет и реагирует на '
        'жалобы жителей. В основе лежат упрощённые модели пассажиропотока и '
        'расписаний.',
    ),
    (
        'Аудиогид для людей с нарушениями зрения',
        'health',
        Idea.IN_PROGRESS,
        Idea.PUBLIC,
        'доступность, аудио, город',
        'Голосовые экскурсии, которые помогают ориентироваться в городе.',
        'Сервис сочетает аудиоописания достопримечательностей с подсказками по '
        'маршруту. Материалы записываются с участием незрячих консультантов и '
        'тестируются на реальных прогулках.',
    ),
    (
        'Платформа менторства для студентов',
        'education',
        Idea.PUBLISHED,
        Idea.PUBLIC,
        'менторство, студенты, карьера',
        'Подбор наставников и структурированные встречи для студентов.',
        'Платформа помогает студентам найти ментора по интересам, согласовать '
        'цели и вести журнал встреч. Университеты получают обезличенную '
        'статистику о запросах учащихся.',
    ),
    (
        'Календарь привычек с поддержкой друзей',
        'productivity',
        Idea.PUBLISHED,
        Idea.PUBLIC,
        'привычки, продуктивность, друзья',
        'Трекер привычек, в котором близкие помогают не сдаваться.',
        'Пользователь выбирает небольшие ежедневные действия и приглашает '
        'друзей для поддержки. Вместо публичных рейтингов сервис делает акцент '
        'на личном прогрессе и бережных напоминаниях.',
    ),
    (
        'Обмен инструментами между соседями',
        'community',
        Idea.PUBLISHED,
        Idea.PUBLIC,
        'соседи, аренда, сообщество',
        'Сервис, который помогает одалживать редкие инструменты рядом с домом.',
        'Жители одного района могут делиться дрелью, лестницей или садовым '
        'инвентарём. Встроенная система бронирования и отзывов снижает риск '
        'неприятных ситуаций.',
    ),
    (
        'Аналитика выбросов для малых производств',
        'environment',
        Idea.IN_PROGRESS,
        Idea.PUBLIC,
        'экология, производство, аналитика',
        'Простой способ оценить выбросы и найти точки для экономии ресурсов.',
        'Сервис собирает данные о расходе энергии и материалов, показывает '
        'динамику выбросов и предлагает практические меры. Отчёты можно '
        'использовать для внутреннего планирования.',
    ),
    (
        'Библиотека звуков для подкастеров',
        'technology',
        Idea.COMPLETED,
        Idea.PUBLIC,
        'аудио, подкасты, библиотека',
        'Коллекция свободных звуков и музыкальных фрагментов для аудиопроектов.',
        'Библиотека содержит короткие звуки окружения, переходы и фоновые '
        'фрагменты с понятными условиями использования. Авторы могут '
        'загружать свои записи и получать обратную связь.',
    ),
    (
        'Конструктор школьных проектов',
        'education',
        Idea.PUBLISHED,
        Idea.PUBLIC,
        'школа, проекты, конструктор',
        'Помощник для учителей, который собирает учебный проект по шагам.',
        'Конструктор предлагает структуру проекта, критерии оценивания и '
        'шаблоны для командной работы. Учитель может адаптировать материалы '
        'под свой предмет и возраст учеников.',
    ),
    (
        'Поиск попутчиков на работу',
        'community',
        Idea.DRAFT,
        Idea.PUBLIC,
        'попутчики, транспорт, город',
        'Сервис для совместных поездок по привычным маршрутам.',
        'Приложение помогает коллегам и соседям находить попутчиков на работу '
        'и обратно. Важно продумать проверку профилей, правила безопасности и '
        'удобное планирование повторяющихся поездок.',
    ),
    (
        'Помощник рекрутера с объяснимым ИИ',
        'ai-ml',
        Idea.COMPLETED,
        Idea.PRIVATE,
        'ИИ, рекрутинг, объяснимость',
        'Инструмент, который помогает сравнивать резюме и объясняет выводы.',
        'Система выделяет требования вакансии и показывает, какие фрагменты '
        'резюме на них отвечают. Рекрутер видит основания рекомендации и может '
        'скорректировать критерии, а окончательное решение остаётся за человеком.',
    ),
    (
        'Фермерская полка',
        'business',
        Idea.PUBLISHED,
        Idea.PUBLIC,
        'фермеры, доставка, продукты',
        'Онлайн-витрина небольших хозяйств с доставкой в один день.',
        'Проект помогает фермерам публиковать сезонные продукты и собирать '
        'заказы небольшими партиями. Покупатели видят происхождение товара, '
        'сроки доставки и отзывы соседей.',
    ),
    (
        'Трекер сна с персональными советами',
        'health',
        Idea.IN_PROGRESS,
        Idea.PUBLIC,
        'сон, здоровье, рекомендации',
        'Дневник сна, который превращает наблюдения в понятные шаги.',
        'Пользователь отмечает время сна и самочувствие, а сервис показывает '
        'закономерности и предлагает небольшие изменения. При устойчивых '
        'проблемах приложение рекомендует обратиться к специалисту.',
    ),
]

# (title, category slug, related idea title, status, visibility, description,
#  technologies, needed specialists, creator index)
DEMO_PROJECTS = [
    (
        'Умею: обмен навыками',
        'community',
        'Платформа обмена навыками «Умею»',
        Project.ACTIVE,
        Project.PUBLIC,
        'Развиваем платформу обмена навыками: готовим каталог предложений, '
        'календарь занятий и первые пилотные пары участников.',
        'Django, PostgreSQL, HTMX',
        'Разработчик, дизайнер, специалист по сообществу',
        0,
    ),
    (
        'Уроки под контролем ИИ',
        'ai-ml',
        'Нейросеть для проверки домашних заданий',
        Project.ACTIVE,
        Project.PUBLIC,
        'Пилотный проект с двумя школами: проверяем, как модель помогает '
        'учителю экономить время и не терять качество обратной связи.',
        'Python, PyTorch, FastAPI',
        'ML-инженер, методист, учитель-эксперт',
        12,
    ),
    (
        'Экокарта города',
        'environment',
        'Карта раздельного сбора отходов',
        Project.PLANNING,
        Project.PUBLIC,
        'Собираем данные о пунктах приёма вторсырья и готовим первую карту '
        'для трёх районов города.',
        'Django, Leaflet, PostgreSQL',
        'Разработчик, исследователь, координатор волонтёров',
        7,
    ),
    (
        'Бюджет семьи 2.0',
        'business',
        'Помощник семейного бюджета',
        Project.COMPLETED,
        Project.PUBLIC,
        'Завершили основную версию семейного бюджета: конверты, напоминания '
        'и месячные отчёты. Сейчас собираем пожелания для следующего релиза.',
        'Django, JavaScript, Chart.js',
        'Разработчик, финансист, тестировщик',
        4,
    ),
    (
        'Дизайн-система «Основа»',
        'design',
        'Генератор дизайн-систем для стартапов',
        Project.PAUSED,
        Project.PUBLIC,
        'Собираем библиотеку компонентов для небольших продуктовых команд. '
        'Проект на паузе до появления свободного дизайнера.',
        'Figma, TypeScript, Storybook',
        'Дизайнер, фронтенд-разработчик',
        5,
    ),
    (
        'Доступный аудиогид',
        'health',
        'Аудиогид для людей с нарушениями зрения',
        Project.ACTIVE,
        Project.PUBLIC,
        'Готовим аудиогид по центру города вместе с незрячими консультантами '
        'и проверяем маршрут на практике.',
        'Django, мобильное аудио, OpenStreetMap',
        'Разработчик, аудиоредактор, консультант по доступности',
        9,
    ),
    (
        'Менторская сеть вузов',
        'education',
        'Платформа менторства для студентов',
        Project.PLANNING,
        Project.PUBLIC,
        'Проектируем пилотную менторскую программу для трёх университетов '
        'и описываем правила сопровождения участников.',
        'Django, PostgreSQL, календарь',
        'Методист, продюсер, разработчик',
        13,
    ),
    (
        'Привычки вместе',
        'productivity',
        'Календарь привычек с поддержкой друзей',
        Project.ACTIVE,
        Project.PUBLIC,
        'Делаем трекер привычек с бережными напоминаниями и поддержкой друзей. '
        'Сейчас тестируем сценарии на небольшой группе пользователей.',
        'Django, HTMX, Alpine.js',
        'Разработчик, дизайнер, исследователь',
        10,
    ),
    (
        'Фермерская полка',
        'business',
        'Фермерская полка',
        Project.COMPLETED,
        Project.PUBLIC,
        'Запустили витрину для пяти небольших хозяйств и отработали доставку '
        'в пределах города. Продолжаем собирать обратную связь покупателей.',
        'Django, PostgreSQL, карты',
        'Разработчик, операционный менеджер, маркетолог',
        3,
    ),
    (
        'Сон под контролем',
        'health',
        'Трекер сна с персональными советами',
        Project.PLANNING,
        Project.PRIVATE,
        'Исследуем, как аккуратно показывать пользователю закономерности сна '
        'и не давать медицинских обещаний. Ищем консультанта-сомнолога.',
        'Django, Python, визуализация',
        'Исследователь, разработчик, консультант по сну',
        8,
    ),
]

COMMENT_TEXTS = [
    'Очень полезная идея, особенно для небольших команд.',
    'Как вы планируете проверять точность рекомендаций?',
    'Мне не хватает подробностей о том, как будет храниться история.',
    'Похоже на сервис, которым я пользовался бы каждый день.',
    'Стоит добавить офлайн-режим для поездок без интернета.',
    'Нравится акцент на бережных напоминаниях вместо рейтингов.',
    'Какая аудитория для вас приоритетна на первом этапе?',
    'Хорошо бы предусмотреть экспорт данных в открытом формате.',
    'Идея сильная, но важно продумать приватность по умолчанию.',
    'Можно начать с одного района и проверить спрос на практике.',
    'Уже вижу, как это пригодилось бы моим знакомым.',
    'Было бы здорово добавить примеры реальных сценариев.',
    'Непонятно, как будет работать модерация пользовательского контента.',
    'Поддерживаю проект, особенно если появится мобильная версия.',
    'Для пилота стоит выбрать две-три школы и сравнить результаты.',
    'Как вы собираетесь измерять пользу для пользователей?',
    'Мне кажется, здесь пригодится интеграция с календарём.',
    'Важно, чтобы рекомендации были объяснимыми, а не «чёрным ящиком».',
    'Хорошая ниша, но конкуренты уже есть — чем вы отличаетесь?',
    'Добавьте, пожалуйста, возможность работать в команде.',
    'Идея выглядит реалистичной для небольшого MVP.',
    'Особенно ценю внимание к доступности интерфейса.',
    'Можно ли будет пользоваться сервисом без регистрации?',
    'Понравился фокус на локальные сообщества и соседей.',
    'Стоит заранее описать правила безопасности для встреч.',
    'Какой стек вы планируете использовать для первой версии?',
    'Было бы полезно увидеть карту текущих партнёров.',
    'Готов помочь с тестированием, если понадобится.',
    'Хорошо, что проект не обещает лишнего и честно говорит о границах.',
    'Желаю команде удачи, тема действительно важная.',
]

def _build_pairs(idea_total, per_idea, user_total, seed):
    """Build unique (idea, user) pairs where nobody reacts to own idea."""
    pairs = []
    for idea_index in range(idea_total):
        author_index = idea_index % user_total
        added = 0
        step = 0
        while added < per_idea:
            user_index = (idea_index * seed + step) % user_total
            step += 1
            if user_index == author_index:
                continue
            pair = (idea_index, user_index)
            if pair in pairs:
                continue
            pairs.append(pair)
            added += 1
    return pairs


# Deterministic pairs: two different readers per idea, 20 * 2 = 40 likes.
LIKE_PAIRS = _build_pairs(20, 2, len(DEMO_USERS), 7)

# One favorite from a different user for each of the first 15 ideas.
FAVORITE_PAIRS = _build_pairs(15, 1, len(DEMO_USERS), 5)

MEMBER_ROLES = [
    ProjectMember.DEVELOPER,
    ProjectMember.DESIGNER,
    ProjectMember.RESEARCHER,
]


class Command(BaseCommand):
    help = (
        'Создаёт реалистичные демонстрационные данные IdeaMix. '
        'Повторный запуск не создаёт дубликаты и не удаляет записи.'
    )

    def handle(self, *args, **options):
        counts = {
            'categories': 0,
            'users': 0,
            'profiles': 0,
            'ideas': 0,
            'projects': 0,
            'members': 0,
            'comments': 0,
            'likes': 0,
            'favorites': 0,
        }

        try:
            with transaction.atomic():
                categories = self._seed_categories(counts)
                users = self._seed_users(counts)
                ideas = self._seed_ideas(categories, users, counts)
                projects = self._seed_projects(categories, ideas, users, counts)
                self._seed_members(projects, users, counts)
                self._seed_comments(ideas, users, counts)
                self._seed_likes(ideas, users, counts)
                self._seed_favorites(ideas, users, counts)
        except (ValidationError, IntegrityError) as exc:
            raise CommandError(
                'Не удалось заполнить демонстрационные данные. '
                'Все изменения отменены, существующие записи не затронуты. '
                f'Причина: {self._error_text(exc)}'
            ) from exc

        self.stdout.write(self.style.SUCCESS(
            'Демонстрационные данные IdeaMix готовы.'
        ))
        self.stdout.write(f'  Категории: создано {counts["categories"]}.')
        self.stdout.write(f'  Пользователи: создано {counts["users"]}.')
        self.stdout.write(f'  Профили: обновлено {counts["profiles"]}.')
        self.stdout.write(f'  Идеи: создано {counts["ideas"]}.')
        self.stdout.write(f'  Проекты: создано {counts["projects"]}.')
        self.stdout.write(f'  Участники проектов: создано {counts["members"]}.')
        self.stdout.write(f'  Комментарии: создано {counts["comments"]}.')
        self.stdout.write(f'  Лайки: создано {counts["likes"]}.')
        self.stdout.write(f'  Избранное: создано {counts["favorites"]}.')
        self.stdout.write(
            'Повторный запуск безопасен: существующие записи не удаляются '
            'и не дублируются.'
        )

    def _seed_categories(self, counts):
        categories = {}
        for name, slug, icon, description in DEMO_CATEGORIES:
            category = Category.objects.filter(slug=slug).first()
            if category is None:
                category = Category.objects.filter(name=name).first()
            if category is None:
                category = Category(
                    name=name,
                    slug=slug,
                    icon=icon,
                    description=description,
                )
                category.full_clean()
                category.save()
                counts['categories'] += 1
            categories[slug] = category
        return categories

    def _seed_users(self, counts):
        users = []
        for data in DEMO_USERS:
            user = User.objects.filter(username=data['username']).first()
            if user is None:
                user = User(
                    username=data['username'],
                    email=data['email'],
                    first_name=data['first_name'],
                    last_name=data['last_name'],
                )
                user.set_unusable_password()
                user.full_clean()
                user.save()
                counts['users'] += 1
            elif user.is_staff or user.is_superuser:
                self.stderr.write(self.style.WARNING(
                    f'Внимание: существующий пользователь {user.username} '
                    'имеет административные права. Команда не изменяет его.'
                ))

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.bio = data['bio']
            profile.location = data['location']
            profile.skills = data['skills']
            profile.website = ''
            profile.full_clean()
            profile.save()
            counts['profiles'] += 1
            users.append(user)
        return users

    def _seed_ideas(self, categories, users, counts):
        ideas = []
        for index, item in enumerate(DEMO_IDEAS):
            (
                title,
                category_slug,
                status,
                visibility,
                tags,
                short_description,
                description,
            ) = item
            author = users[index % len(users)]
            idea = Idea.objects.filter(author=author, title=title).first()
            if idea is None:
                idea = Idea(
                    author=author,
                    title=title,
                    short_description=short_description,
                    description=description,
                    category=categories[category_slug],
                    tags=tags,
                    status=status,
                    visibility=visibility,
                )
                idea.full_clean()
                idea.save()
                counts['ideas'] += 1
            else:
                # Demo content stays consistent on repeated runs, while the
                # historical record itself is preserved and never duplicated.
                idea.short_description = short_description
                idea.description = description
                idea.category = categories[category_slug]
                idea.tags = tags
                idea.status = status
                idea.visibility = visibility
                idea.full_clean()
                idea.save()
            ideas.append(idea)
        return ideas

    def _seed_projects(self, categories, ideas, users, counts):
        idea_by_title = {idea.title: idea for idea in ideas}
        projects = []
        for item in DEMO_PROJECTS:
            (
                title,
                category_slug,
                idea_title,
                status,
                visibility,
                description,
                technologies,
                needed_specialists,
                creator_index,
            ) = item
            creator = users[creator_index % len(users)]
            project = Project.objects.filter(creator=creator, title=title).first()
            if project is None:
                project = Project(
                    creator=creator,
                    title=title,
                    description=description,
                    related_idea=idea_by_title.get(idea_title),
                    category=categories[category_slug],
                    status=status,
                    technologies=technologies,
                    needed_specialists=needed_specialists,
                    visibility=visibility,
                    is_open=True,
                )
                project.full_clean()
                project.save()
                counts['projects'] += 1
            related_idea = idea_by_title.get(idea_title)
            if related_idea is not None:
                project.ideas.add(related_idea)
            projects.append(project)
        return projects

    def _seed_members(self, projects, users, counts):
        for index, project in enumerate(projects):
            member_ids = [users.index(project.creator)]
            for offset in (1, 5, 9):
                candidate = (index + offset) % len(users)
                if candidate not in member_ids:
                    member_ids.append(candidate)
            for position, user_index in enumerate(member_ids):
                user = users[user_index]
                membership = ProjectMember.objects.filter(
                    project=project, user=user
                ).first()
                if membership is None:
                    role = (
                        ProjectMember.OWNER
                        if user_index == users.index(project.creator)
                        else MEMBER_ROLES[(index + position) % len(MEMBER_ROLES)]
                    )
                    membership = ProjectMember(
                        project=project,
                        user=user,
                        role=role,
                    )
                    membership.full_clean()
                    membership.save()
                    counts['members'] += 1

    def _seed_comments(self, ideas, users, counts):
        commentable = [idea for idea in ideas if idea.status != Idea.DRAFT]
        for index, text in enumerate(COMMENT_TEXTS):
            idea = commentable[index % len(commentable)]
            author = users[(index * 3 + 1) % len(users)]
            if author.pk == idea.author_id:
                author = users[(index * 3 + 2) % len(users)]
            comment = Comment.objects.filter(
                idea=idea, author=author, text=text
            ).first()
            if comment is None:
                comment = Comment(idea=idea, author=author, text=text)
                comment.full_clean()
                comment.save()
                counts['comments'] += 1

    def _seed_likes(self, ideas, users, counts):
        for idea_index, user_index in LIKE_PAIRS:
            idea = ideas[idea_index]
            user = users[user_index]
            like = IdeaLike.objects.filter(idea=idea, user=user).first()
            if like is None:
                like = IdeaLike(idea=idea, user=user)
                like.full_clean()
                like.save()
                counts['likes'] += 1

    def _seed_favorites(self, ideas, users, counts):
        for idea_index, user_index in FAVORITE_PAIRS:
            idea = ideas[idea_index]
            user = users[user_index]
            favorite = Favorite.objects.filter(idea=idea, user=user).first()
            if favorite is None:
                favorite = Favorite(idea=idea, user=user)
                favorite.full_clean()
                favorite.save()
                counts['favorites'] += 1

    @staticmethod
    def _error_text(exc):
        if isinstance(exc, ValidationError):
            if hasattr(exc, 'message_dict'):
                parts = []
                for field, messages in exc.message_dict.items():
                    parts.append(f'{field}: {" ".join(messages)}')
                return '; '.join(parts)
            return ' '.join(exc.messages)
        return str(exc)
