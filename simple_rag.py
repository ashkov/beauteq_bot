# simple_rag.py
import re
import sqlite3
from typing import List, Dict


class SimpleRAG:
    def __init__(self, db_path: str = "data/knowledge.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Простая текстовая база знаний"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY,
                    category TEXT,
                    keywords TEXT,  
                    content TEXT    
                )
            """)
            self._seed_data(conn)

    def _seed_data(self, conn):
        """Начальные данные о салоне"""
        knowledge = [
            {
                "category": "скидки",
                "keywords": "студент скидка акция льгота",
                "content": "Студентам предоставляется скидка 10% в будние дни с 10:00 до 16:00 при предъявлении студенческого билета"
            },
            {
                "category": "дети",
                "keywords": "ребенок дети детский малыш",
                "content": "Да, у нас есть детская зона с игрушками и няней на 2 часа бесплатно для клиентов салона"
            },
            {
                "category": "парковка",
                "keywords": "парковка машина авто parking",
                "content": "У салона есть бесплатная парковка на 10 машиномест. Первые 2 часа бесплатно для наших клиентов"
            },
            {
                "category": "бренды",
                "keywords": "бренд косметика марка производитель",
                "content": "Мы работаем с премиальными брендами: L'Oreal Professionnel для волос, Christina для косметологии, OPI для маникюра"
            },
            {
                "category": "запись",
                "keywords": "отмена перенос отменить запись",
                "content": "Отмена бесплатна за 24 часа до визита. При отмене позднее предусмотрена комиссия 50% от стоимости услуги"
            }
        ]

        for item in knowledge:
            conn.execute(
                "INSERT OR IGNORE INTO knowledge (category, keywords, content) VALUES (?, ?, ?)",
                (item["category"], item["keywords"], item["content"])
            )

    def search(self, query: str, top_k: int = 2) -> List[Dict]:
        """Простой поиск по ключевым словам"""
        query_words = set(re.findall(r'\w+', query.lower()))

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM knowledge")
            results = []

            for row in cursor:
                keywords = set(re.findall(r'\w+', row['keywords'].lower()))
                # Считаем совпадения слов
                matches = len(query_words.intersection(keywords))
                if matches > 0:
                    results.append({
                        "content": row['content'],
                        "score": matches,
                        "category": row['category']
                    })

            # Сортируем по количеству совпадений
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]
