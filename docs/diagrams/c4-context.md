C4Context
    title C4 Context: AI Day Planner System

    Person(user, "User", "Владелец расписания")
    System(planner, "AI Day Planner", "Агент планирования дня")
    
    System_Ext(llm, "LLM Provider", "OpenAI / Anthropic")
    System_Ext(calendar, "Google Calendar", "Календарь пользователя")
    System_Ext(weather, "Weather API", "Погода для оффлайн активностей")

    Rel(user, planner, "Отправляет задачи текстом / голосом", "Telegram/Web")
    Rel(planner, llm, "Промпты, вызов тулов", "REST/gRPC")
    Rel(planner, calendar, "Чтение слотов, запись событий", "OAuth2/REST")
    Rel(planner, weather, "Запрос прогноза", "REST")
