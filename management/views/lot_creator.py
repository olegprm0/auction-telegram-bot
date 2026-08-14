"""
Создатель лотов
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List

from PyQt5.QtCore import QDateTime, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from database.db import SessionLocal
from database.models import DocumentType, Lot, LotStatus, User, UserRole

logger = logging.getLogger(__name__)


class LotCreator(QWidget):
    """Создатель лотов"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.selected_images = []
        self.selected_files = []
        self.init_ui()

    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout(self)

        # Заголовок
        title = QLabel("Создание нового лота")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Основная форма
        form_group = QGroupBox("Основная информация")
        form_layout = QFormLayout(form_group)

        # Название лота
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Введите название лота")
        form_layout.addRow("Название:", self.title_edit)

        # Описание
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setPlaceholderText("Введите описание лота")
        form_layout.addRow("Описание:", self.description_edit)

        # Стартовая цена
        self.starting_price_spin = QSpinBox()
        self.starting_price_spin.setRange(1, 1000000000)
        self.starting_price_spin.setValue(1000)
        self.starting_price_spin.setSuffix(" ₽")
        form_layout.addRow("Стартовая цена:", self.starting_price_spin)

        # Тип документа
        self.document_type_combo = QComboBox()
        self.document_type_combo.addItems(
            ["Стандартный", "Ювелирные изделия", "Исторические ценности"]
        )
        form_layout.addRow("Тип документа:", self.document_type_combo)

        layout.addWidget(form_group)

        # Планирование публикации
        schedule_group = QGroupBox("Планирование публикации")
        schedule_layout = QFormLayout(schedule_group)

        # Дата и время начала
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(datetime.now().date())
        schedule_layout.addRow("Дата начала:", self.start_date_edit)

        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setTime(datetime.now().time())
        schedule_layout.addRow("Время начала:", self.start_time_edit)

        # Продолжительность аукциона
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 30)
        self.duration_spin.setValue(7)
        self.duration_spin.setSuffix(" дней")
        schedule_layout.addRow("Продолжительность:", self.duration_spin)

        layout.addWidget(schedule_group)

        # Медиафайлы
        media_group = QGroupBox("Медиафайлы")
        media_layout = QVBoxLayout(media_group)

        # Изображения
        images_layout = QHBoxLayout()
        add_image_btn = QPushButton("Добавить изображения")
        add_image_btn.clicked.connect(self.add_images)
        images_layout.addWidget(add_image_btn)

        clear_images_btn = QPushButton("Очистить")
        clear_images_btn.clicked.connect(self.clear_images)
        images_layout.addWidget(clear_images_btn)

        media_layout.addLayout(images_layout)

        self.images_list = QListWidget()
        self.images_list.setMaximumHeight(100)
        media_layout.addWidget(QLabel("Изображения:"))
        media_layout.addWidget(self.images_list)

        # Файлы
        files_layout = QHBoxLayout()
        add_files_btn = QPushButton("Добавить файлы")
        add_files_btn.clicked.connect(self.add_files)
        files_layout.addWidget(add_files_btn)

        clear_files_btn = QPushButton("Очистить")
        clear_files_btn.clicked.connect(self.clear_files)
        files_layout.addWidget(clear_files_btn)

        media_layout.addLayout(files_layout)

        self.files_list = QListWidget()
        self.files_list.setMaximumHeight(100)
        media_layout.addWidget(QLabel("Файлы:"))
        media_layout.addWidget(self.files_list)

        layout.addWidget(media_group)

        # Дополнительная информация
        additional_group = QGroupBox("Дополнительная информация")
        additional_layout = QFormLayout(additional_group)

        # Геолокация
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Введите адрес или координаты")
        additional_layout.addRow("Геолокация:", self.location_edit)

        # Username продавца
        self.seller_username_edit = QLineEdit()
        self.seller_username_edit.setPlaceholderText("@username или username")
        additional_layout.addRow("Username продавца:", self.seller_username_edit)

        layout.addWidget(additional_group)

        # Кнопки управления
        btn_layout = QHBoxLayout()

        save_btn = QPushButton("Сохранить лот")
        save_btn.clicked.connect(self.save_lot)
        save_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """
        )
        btn_layout.addWidget(save_btn)

        save_draft_btn = QPushButton("Сохранить черновик")
        save_draft_btn.clicked.connect(self.save_draft)
        save_draft_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #f39c12;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
        """
        )
        btn_layout.addWidget(save_draft_btn)

        back_btn = QPushButton("Назад")
        back_btn.clicked.connect(self.go_back)
        btn_layout.addWidget(back_btn)

        layout.addLayout(btn_layout)

        # Предварительный просмотр
        preview_group = QGroupBox("Предварительный просмотр")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        preview_layout.addWidget(self.preview_text)

        layout.addWidget(preview_group)

        # Обновляем предварительный просмотр
        self.update_preview()

        # Подключаем сигналы для обновления предварительного просмотра
        self.title_edit.textChanged.connect(self.update_preview)
        self.description_edit.textChanged.connect(self.update_preview)
        self.starting_price_spin.valueChanged.connect(self.update_preview)

    def add_images(self):
        """Добавляет изображения"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите изображения",
            "",
            "Изображения (*.jpg *.jpeg *.png *.gif *.bmp)",
        )

        if files:
            for file_path in files:
                self.selected_images.append(file_path)
                item = QListWidgetItem(file_path.split("/")[-1])
                self.images_list.addItem(item)

    def clear_images(self):
        """Очищает список изображений"""
        self.selected_images.clear()
        self.images_list.clear()

    def add_files(self):
        """Добавляет файлы"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Выберите файлы", "", "Все файлы (*.*)"
        )

        if files:
            for file_path in files:
                self.selected_files.append(file_path)
                item = QListWidgetItem(file_path.split("/")[-1])
                self.files_list.addItem(item)

    def clear_files(self):
        """Очищает список файлов"""
        self.selected_files.clear()
        self.files_list.clear()

    def update_preview(self):
        """Обновляет предварительный просмотр"""
        title = self.title_edit.text() or "Название лота"
        description = self.description_edit.toPlainText() or "Описание лота"
        price = self.starting_price_spin.value()
        doc_type = self.document_type_combo.currentText()

        preview_text = f"""
🏷️ {title}

📝 {description}

💰 Стартовая цена: {price:,} ₽
📄 Тип документа: {doc_type}
📅 Дата начала: {self.start_date_edit.date().toString('dd.MM.yyyy')} в {self.start_time_edit.time().toString('HH:mm')}
⏰ Продолжительность: {self.duration_spin.value()} дней

📸 Изображений: {len(self.selected_images)}
📎 Файлов: {len(self.selected_files)}
        """

        self.preview_text.setText(preview_text.strip())

    def save_lot(self):
        """Сохраняет лот"""
        if not self.validate_form():
            return

        db = SessionLocal()
        try:
            # Получаем текущего пользователя
            current_user = self.main_window.get_current_user()
            if not current_user:
                QMessageBox.critical(self, "Ошибка", "Пользователь не авторизован")
                return

            # Находим пользователя в базе
            user = db.query(User).filter(User.role == UserRole.MODERATOR).first()
            if not user:
                QMessageBox.critical(self, "Ошибка", "Модератор не найден")
                return

            # Создаем дату и время начала
            start_date = self.start_date_edit.date().toPyDate()
            start_time = self.start_time_edit.time().toPyTime()
            start_datetime = datetime.combine(start_date, start_time)

            # Make timezone-aware
            from datetime import timezone

            start_datetime = start_datetime.replace(tzinfo=timezone.utc)

            # Создаем дату окончания
            end_datetime = start_datetime + timedelta(days=self.duration_spin.value())

            # Определяем тип документа
            doc_type_map = {
                "Стандартный": DocumentType.STANDARD,
                "Ювелирные изделия": DocumentType.JEWELRY,
                "Исторические ценности": DocumentType.HISTORICAL,
            }
            document_type = doc_type_map.get(
                self.document_type_combo.currentText(), DocumentType.STANDARD
            )

            # Создаем лот
            lot = Lot(
                title=self.title_edit.text(),
                description=self.description_edit.toPlainText(),
                starting_price=self.starting_price_spin.value(),
                current_price=self.starting_price_spin.value(),
                seller_id=user.id,
                start_time=start_datetime,
                end_time=end_datetime,
                status=LotStatus.PENDING,  # На модерации
                document_type=document_type,
                images=(
                    json.dumps(self.selected_images) if self.selected_images else None
                ),
                files=json.dumps(self.selected_files) if self.selected_files else None,
                location=self.location_edit.text() or None,
                seller_link=self._format_seller_link(self.seller_username_edit.text())
                or None,
                min_bid_increment=1.0,  # Минимальный шаг ставки
            )

            db.add(lot)
            db.commit()

            QMessageBox.information(
                self,
                "Успех",
                f"Лот '{lot.title}' создан и отправлен на модерацию.\n"
                f"Публикация запланирована на {start_datetime.strftime('%d.%m.%Y в %H:%M')}",
            )

            # Очищаем форму
            self.clear_form()

        except Exception as e:
            logger.error(f"Ошибка при сохранении лота: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении лота: {e}")
        finally:
            db.close()

    def save_draft(self):
        """Сохраняет черновик"""
        if not self.title_edit.text():
            QMessageBox.warning(self, "Предупреждение", "Введите название лота")
            return

        db = SessionLocal()
        try:
            # Получаем текущего пользователя
            current_user = self.main_window.get_current_user()
            if not current_user:
                QMessageBox.critical(self, "Ошибка", "Пользователь не авторизован")
                return

            # Находим пользователя в базе
            user = db.query(User).filter(User.role == UserRole.MODERATOR).first()
            if not user:
                QMessageBox.critical(self, "Ошибка", "Модератор не найден")
                return

            # Создаем черновик
            lot = Lot(
                title=self.title_edit.text(),
                description=self.description_edit.toPlainText(),
                starting_price=self.starting_price_spin.value(),
                current_price=self.starting_price_spin.value(),
                seller_id=user.id,
                status=LotStatus.DRAFT,  # Черновик
                images=(
                    json.dumps(self.selected_images) if self.selected_images else None
                ),
                files=json.dumps(self.selected_files) if self.selected_files else None,
                location=self.location_edit.text() or None,
                seller_link=self._format_seller_link(self.seller_username_edit.text())
                or None,
                min_bid_increment=1.0,
            )

            db.add(lot)
            db.commit()

            QMessageBox.information(
                self,
                "Успех",
                f"Черновик '{lot.title}' сохранен.\n"
                f"Вы можете отредактировать его позже.",
            )

            # Очищаем форму
            self.clear_form()

        except Exception as e:
            logger.error(f"Ошибка при сохранении черновика: {e}")
            QMessageBox.critical(
                self, "Ошибка", f"Ошибка при сохранении черновика: {e}"
            )
        finally:
            db.close()

    def validate_form(self):
        """Проверяет корректность формы"""
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Предупреждение", "Введите название лота")
            return False

        if not self.description_edit.toPlainText().strip():
            QMessageBox.warning(self, "Предупреждение", "Введите описание лота")
            return False

        if self.starting_price_spin.value() <= 0:
            QMessageBox.warning(
                self, "Предупреждение", "Стартовая цена должна быть больше 0"
            )
            return False

        # Проверяем, что дата начала не в прошлом
        start_date = self.start_date_edit.date().toPyDate()
        start_time = self.start_time_edit.time().toPyTime()
        start_datetime = datetime.combine(start_date, start_time)

        if start_datetime < datetime.now():
            QMessageBox.warning(
                self, "Предупреждение", "Дата начала не может быть в прошлом"
            )
            return False

        # Валидация ссылки на продавца: допускаем пусто или https://t.me/<username>
        seller_username = (self.seller_username_edit.text() or "").strip()
        if seller_username:
            # Уберем пробелы/служебные и сформируем валидную ссылку
            import re

            cleaned = seller_username.lstrip("@ ")
            # username: латиница/цифры/подчерк, 5-32 символов (как в Telegram)
            if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", cleaned):
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    "Username продавца должен содержать 5-32 символов: латиница, цифры или подчёркивание",
                )
                return False
        return True

    def clear_form(self):
        """Очищает форму"""
        self.title_edit.clear()
        self.description_edit.clear()
        self.starting_price_spin.setValue(1000)
        self.document_type_combo.setCurrentIndex(0)
        self.start_date_edit.setDate(datetime.now().date())
        self.start_time_edit.setTime(datetime.now().time())
        self.duration_spin.setValue(7)
        self.location_edit.clear()
        self.seller_username_edit.clear()
        self.clear_images()
        self.clear_files()
        self.update_preview()

    def _format_seller_link(self, username: str) -> str:
        """Форматирует username в ссылку на продавца"""
        if not username:
            return None

        # Очищаем username от @ если есть
        clean_username = username.lstrip("@")

        # Проверяем, что username не пустой
        if not clean_username:
            return None

        # Возвращаем ссылку в формате https://t.me/username
        return f"https://t.me/{clean_username}"

    def go_back(self):
        """Возвращается к предыдущей панели"""
        current_user = self.main_window.get_current_user()
        if current_user:
            if current_user["role"] == UserRole.MODERATOR:
                self.main_window.content_stack.setCurrentIndex(
                    1
                )  # Панель администратора
            elif current_user["role"] == UserRole.SUPPORT:
                self.main_window.content_stack.setCurrentIndex(2)  # Панель модерации
            elif current_user["role"] == UserRole.SUPER_ADMIN:
                self.main_window.content_stack.setCurrentIndex(
                    3
                )  # Панель супер-администратора
        else:
            self.main_window.content_stack.setCurrentIndex(0)  # Панель входа
