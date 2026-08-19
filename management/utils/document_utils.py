"""
Утилиты для работы с документами лотов
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from database.models import DocumentType, Lot, LotStatus

logger = logging.getLogger(__name__)


def format_local_time(dt):
    """Форматирует время по МСК (Europe/Moscow)."""
    if dt is None:
        return "Не указано"
    try:
        # Используем общую утилиту для приведения к МСК, если доступна
        try:
            from bot.utils.time_utils import utc_to_moscow

            msk = utc_to_moscow(dt)
            return msk.strftime("%d.%m.%Y %H:%M")
        except Exception:
            # Фолбэк: если tz отсутствует, считаем, что уже МСК
            if getattr(dt, "tzinfo", None) is not None:
                # Приводим к offset-naive строке, сохранив локальное время
                return dt.astimezone().strftime("%d.%m.%Y %H:%M")
            return dt.strftime("%d.%m.%Y %H:%M")
    except Exception as e:
        logger.error(f"Ошибка при форматировании времени: {e}")
        return "Ошибка времени"


class DocumentGenerator:
    """Генератор документов для лотов"""

    @staticmethod
    def generate_lot_report(lot: Lot, format_type: str = "txt") -> str:
        """Генерирует отчет о лоте в указанном формате"""
        if format_type == "html":
            return DocumentGenerator._generate_html_report(lot)
        else:
            return DocumentGenerator._generate_text_report(lot)

    @staticmethod
    def _generate_text_report(lot: Lot) -> str:
        """Генерирует текстовый отчет о лоте"""
        status_text = {
            LotStatus.DRAFT: "Черновик",
            LotStatus.PENDING: "На модерации",
            LotStatus.ACTIVE: "Активен",
            LotStatus.SOLD: "Продан",
            LotStatus.CANCELLED: "Отменен",
            LotStatus.EXPIRED: "Истек",
        }.get(lot.status, "Неизвестно")

        content = f"""
ОТЧЕТ О ЛОТЕ
=============

ID: {lot.id}
Название: {lot.title}
Описание: {lot.description}
Стартовая цена: {lot.starting_price:,.2f} ₽
Текущая цена: {lot.current_price:,.2f} ₽
Статус: {status_text}
Время старта: {format_local_time(lot.start_time) if lot.start_time else "Немедленно"}
Время окончания: {format_local_time(lot.end_time) if lot.end_time else "Не определено"}
Создан: {format_local_time(lot.created_at)}

"""

        if lot.location:
            content += f"Геолокация: {lot.location}\n"
        if lot.seller_link:
            content += f"Ссылка продавца: {lot.seller_link}\n"

        if lot.bids:
            content += f"\nСТАТИСТИКА СТАВОК\n"
            content += f"================\n"
            content += f"Всего ставок: {len(lot.bids)}\n"
            max_bid = max([bid.amount for bid in lot.bids]) if lot.bids else 0
            content += f"Максимальная ставка: {max_bid:,.2f} ₽\n"
            unique_bidders = len(set([bid.bidder_id for bid in lot.bids]))
            content += f"Уникальных участников: {unique_bidders}\n"

            # Последние ставки
            recent_bids = sorted(lot.bids, key=lambda x: x.created_at, reverse=True)[
                :10
            ]
            if recent_bids:
                content += f"\nПОСЛЕДНИЕ СТАВКИ\n"
                content += f"================\n"
                for i, bid in enumerate(recent_bids, 1):
                    content += f"{i}. {bid.amount:,.2f} ₽ ({format_local_time(bid.created_at)})\n"

        return content

    @staticmethod
    def _generate_html_report(lot: Lot) -> str:
        """Генерирует HTML отчет о лоте"""
        status_text = {
            LotStatus.DRAFT: "Черновик",
            LotStatus.PENDING: "На модерации",
            LotStatus.ACTIVE: "Активен",
            LotStatus.SOLD: "Продан",
            LotStatus.CANCELLED: "Отменен",
            LotStatus.EXPIRED: "Истек",
        }.get(lot.status, "Неизвестно")

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Отчет о лоте {lot.id} - {lot.title}</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 20px; 
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{ 
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white; 
            padding: 30px; 
            border-radius: 10px; 
            margin-bottom: 30px;
            text-align: center;
        }}
        .info {{ 
            background-color: #f8f9fa; 
            padding: 25px; 
            margin: 20px 0; 
            border-radius: 10px;
            border-left: 5px solid #007bff;
        }}
        .status {{ 
            padding: 8px 15px; 
            border-radius: 5px; 
            font-weight: bold; 
            display: inline-block;
        }}
        .status-draft {{ background-color: #6c757d; color: white; }}
        .status-pending {{ background-color: #fff3cd; color: #856404; }}
        .status-active {{ background-color: #d4edda; color: #155724; }}
        .status-sold {{ background-color: #f8d7da; color: #721c24; }}
        .status-cancelled {{ background-color: #f8d7da; color: #721c24; }}
        .status-expired {{ background-color: #e2e3e5; color: #383d41; }}
        .stats {{ 
            background-color: #e9ecef; 
            padding: 25px; 
            margin: 20px 0; 
            border-radius: 10px;
            border-left: 5px solid #28a745;
        }}
        .bids-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        .bids-table th, .bids-table td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        .bids-table th {{
            background-color: #007bff;
            color: white;
        }}
        .bids-table tr:nth-child(even) {{
            background-color: #f2f2f2;
        }}
        .price {{
            font-weight: bold;
            color: #28a745;
        }}
        .timestamp {{
            color: #6c757d;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📦 Отчет о лоте</h1>
            <h2>Лот {lot.id}: {lot.title}</h2>
        </div>
        
        <div class="info">
            <h2>📋 Информация о лоте</h2>
            <table style="width: 100%;">
                <tr>
                    <td><strong>ID:</strong></td>
                    <td>{lot.id}</td>
                </tr>
                <tr>
                    <td><strong>Название:</strong></td>
                    <td>{lot.title}</td>
                </tr>
                <tr>
                    <td><strong>Описание:</strong></td>
                    <td>{lot.description}</td>
                </tr>
                <tr>
                    <td><strong>Стартовая цена:</strong></td>
                    <td class="price">{lot.starting_price:,.2f} ₽</td>
                </tr>
                <tr>
                    <td><strong>Текущая цена:</strong></td>
                    <td class="price">{lot.current_price:,.2f} ₽</td>
                </tr>
                <tr>
                    <td><strong>Статус:</strong></td>
                    <td><span class="status status-{lot.status.value}">{status_text}</span></td>
                </tr>
                <tr>
                    <td><strong>Время старта:</strong></td>
                    <td>{format_local_time(lot.start_time) if lot.start_time else "Немедленно"}</td>
                </tr>
                <tr>
                    <td><strong>Время окончания:</strong></td>
                    <td>{format_local_time(lot.end_time) if lot.end_time else "Не определено"}</td>
                </tr>
                <tr>
                    <td><strong>Создан:</strong></td>
                    <td>{format_local_time(lot.created_at)}</td>
                </tr>
"""

        if lot.location:
            html += f"""
                <tr>
                    <td><strong>Геолокация:</strong></td>
                    <td>{lot.location}</td>
                </tr>
"""
        if lot.seller_link:
            html += f"""
                <tr>
                    <td><strong>Ссылка продавца:</strong></td>
                    <td><a href="{lot.seller_link}" target="_blank">{lot.seller_link}</a></td>
                </tr>
"""

        if lot.bids:
            html += f"""
            </table>
        </div>
        
        <div class="stats">
            <h2>💰 Статистика ставок</h2>
            <p><strong>Всего ставок:</strong> {len(lot.bids)}</p>
"""
            max_bid = max([bid.amount for bid in lot.bids]) if lot.bids else 0
            html += f'            <p><strong>Максимальная ставка:</strong> <span class="price">{max_bid:,.2f} ₽</span></p>\n'
            unique_bidders = len(set([bid.bidder_id for bid in lot.bids]))
            html += f"            <p><strong>Уникальных участников:</strong> {unique_bidders}</p>\n"

            # Последние ставки
            recent_bids = sorted(lot.bids, key=lambda x: x.created_at, reverse=True)[
                :10
            ]
            if recent_bids:
                html += f"""
            <h3>Последние ставки</h3>
            <table class="bids-table">
                <thead>
                    <tr>
                        <th>№</th>
                        <th>Сумма</th>
                        <th>Дата и время</th>
                    </tr>
                </thead>
                <tbody>
"""
                for i, bid in enumerate(recent_bids, 1):
                    html += f"""
                    <tr>
                        <td>{i}</td>
                        <td class="price">{bid.amount:,.2f} ₽</td>
                        <td class="timestamp">{format_local_time(bid.created_at)}</td>
                    </tr>
"""
                html += """
                </tbody>
            </table>
"""
        else:
            html += """
            </table>
        </div>
"""

        html += """
    </div>
</body>
</html>
"""

        return html


class ImageManager:
    """Менеджер для работы с изображениями лотов"""

    @staticmethod
    def save_images_for_lot(lot_id: int, image_paths: List[str]) -> List[str]:
        """Сохраняет изображения для лота"""
        if not image_paths:
            return []

        import shutil
        from pathlib import Path

        saved_paths = []
        media_dir = Path("media/lots")
        lot_dir = media_dir / str(lot_id)
        lot_dir.mkdir(parents=True, exist_ok=True)

        for i, image_path in enumerate(image_paths):
            try:
                # Получаем расширение файла
                ext = Path(image_path).suffix
                new_filename = f"image_{i+1}{ext}"
                new_path = lot_dir / new_filename

                # Копируем файл
                shutil.copy2(image_path, new_path)
                saved_paths.append(str(new_path))
            except Exception as e:
                logger.error(f"Ошибка при сохранении изображения {image_path}: {e}")

        return saved_paths

    @staticmethod
    def get_lot_images(lot: Lot) -> List[str]:
        """Получает список изображений лота"""
        if not lot.images:
            return []

        try:
            images_data = json.loads(lot.images)
            return images_data if isinstance(images_data, list) else []
        except Exception as e:
            logger.error(f"Ошибка при загрузке изображений лота {lot.id}: {e}")
            return []

    @staticmethod
    def delete_lot_images(lot_id: int):
        """Удаляет все изображения лота"""
        try:
            import shutil
            from pathlib import Path

            lot_dir = Path("media/lots") / str(lot_id)
            if lot_dir.exists():
                shutil.rmtree(lot_dir)

        except Exception as e:
            logger.error(f"Ошибка при удалении изображений лота {lot_id}: {e}")

    @staticmethod
    def save_files_for_lot(lot_id: int, file_paths: List[str]) -> List[str]:
        """Сохраняет файлы для лота"""
        saved_paths = []

        try:
            import shutil
            from pathlib import Path

            # Создаем директорию для файлов лота
            lot_dir = Path("media/lots") / str(lot_id) / "files"
            lot_dir.mkdir(parents=True, exist_ok=True)

            for file_path in file_paths:
                try:
                    source_path = Path(file_path)
                    if source_path.exists():
                        # Копируем файл в директорию лота
                        dest_path = lot_dir / source_path.name
                        shutil.copy2(source_path, dest_path)
                        saved_paths.append(str(dest_path))
                    else:
                        logger.warning(f"Файл не найден: {file_path}")
                except Exception as e:
                    logger.error(f"Ошибка при сохранении файла {file_path}: {e}")

        except Exception as e:
            logger.error(f"Ошибка при сохранении файлов для лота {lot_id}: {e}")

        return saved_paths

    @staticmethod
    def get_lot_files(lot: Lot) -> List[str]:
        """Получает список файлов лота"""
        if not lot.files:
            return []

        try:
            files_data = json.loads(lot.files)
            return files_data if isinstance(files_data, list) else []
        except Exception as e:
            logger.error(f"Ошибка при загрузке файлов лота {lot.id}: {e}")
            return []

    @staticmethod
    def delete_lot_files(lot_id: int):
        """Удаляет все файлы лота"""
        try:
            import shutil
            from pathlib import Path

            files_dir = Path("media/lots") / str(lot_id) / "files"
            if files_dir.exists():
                shutil.rmtree(files_dir)

        except Exception as e:
            logger.error(f"Ошибка при удалении файлов лота {lot_id}: {e}")


class LotValidator:
    """Валидатор для проверки данных лота"""

    @staticmethod
    def validate_lot_data(data: Dict[str, Any]) -> List[str]:
        """Проверяет данные лота и возвращает список ошибок"""
        errors = []

        # Проверка названия
        if not data.get("title", "").strip():
            errors.append("Название лота обязательно")
        elif len(data.get("title", "").strip()) < 3:
            errors.append("Название лота должно содержать минимум 3 символа")
        elif len(data.get("title", "").strip()) > 200:
            errors.append("Название лота не должно превышать 200 символов")

        # Проверка описания
        if not data.get("description", "").strip():
            errors.append("Описание лота обязательно")
        elif len(data.get("description", "").strip()) < 10:
            errors.append("Описание лота должно содержать минимум 10 символов")

        # Проверка цены
        price = data.get("starting_price", 0)
        if price <= 0:
            errors.append("Стартовая цена должна быть больше 0")
        elif price > 100000000:
    errors.append("Стартовая цена не должна превышать 100,000,000 ₽")

        # Проверка времени старта (если указано)
        start_time = data.get("start_time")
        if start_time is not None:  # Проверяем только если время указано
            now_utc = datetime.now(timezone.utc)
            start_time_utc = start_time
            if getattr(start_time_utc, "tzinfo", None) is None:
                start_time_utc = start_time_utc.replace(tzinfo=timezone.utc)
            if start_time_utc <= now_utc:
                errors.append("Время старта должно быть в будущем")

        return errors

    @staticmethod
    def validate_start_time(start_time) -> list:
        """Проверяет корректность времени старта лота. Возвращает список ошибок."""
        errors = []
        if start_time is not None:
            now_utc = datetime.now(timezone.utc)
            start_time_utc = start_time
            if getattr(start_time_utc, "tzinfo", None) is None:
                start_time_utc = start_time_utc.replace(tzinfo=timezone.utc)
            if start_time_utc <= now_utc:
                errors.append("Время старта должно быть в будущем")
        return errors

    @staticmethod
    def can_edit_lot(lot: Lot) -> bool:
        """Проверяет, можно ли редактировать лот"""
        return lot.status == LotStatus.DRAFT

    @staticmethod
    def can_delete_lot(lot: Lot) -> bool:
        """Проверяет, можно ли удалить лот"""
        return lot.status == LotStatus.DRAFT

    @staticmethod
    def can_submit_for_moderation(lot: Lot) -> bool:
        """Проверяет, можно ли отправить лот на модерацию"""
        if lot.status != LotStatus.DRAFT:
            return False

        # Если время старта не указано (немедленный запуск), то можно отправлять
        if lot.start_time is None:
            return True

        # Если время старта указано, проверяем что оно в будущем (UTC)
        if lot.start_time is not None:
            now_utc = datetime.now(timezone.utc)
            lot_start_utc = lot.start_time
            if getattr(lot_start_utc, "tzinfo", None) is None:
                lot_start_utc = lot_start_utc.replace(tzinfo=timezone.utc)
            if lot_start_utc <= now_utc:
                return False

        return True
