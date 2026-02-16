# 🏢 Inventory & Loan Management System

System do zarządzania zasobami firmowymi (sprzęt, biurka, wypożyczenia) z obsługą ról użytkowników oraz REST API.

Projekt został zbudowany w oparciu o Django i Django REST Framework. Łączy klasyczne widoki HTML z pełnym API.

---

## 🔧 Funkcjonalności

### 👤 Role użytkowników
- **Admin** – pełne zarządzanie systemem
- **Employee** – dostęp tylko do własnych wypożyczeń
- **Company** – wypożyczenia na poziomie biura

Kontrola dostępu oparta na Django Groups oraz dodatkowej walidacji w backendzie.

---

### 📦 Zarządzanie zasobami
- Kategorie sprzętu
- Assety (serial number, status, purchase date)
- Automatyczna zmiana statusu przy wypożyczeniu i zwrocie

Statusy:
- `available`
- `assigned`
- `in_service`
- `retired`

---

### 🏢 Struktura biurowa
- Offices
- Rooms
- Desks
- Departments
- Department positions

---

### 🔄 Wypożyczenia
Możliwość wypożyczenia:
- do osoby
- do biurka
- do biura
- do działu

System:
- sprawdza dostępność sprzętu
- waliduje konflikty biurek
- wykonuje operacje w transakcji
- zapisuje snapshot department
- przy zwrocie przywraca status assetu

---

### 🔍 Filtrowanie i sortowanie
- django-filter
- filtrowanie assetów i pracowników
- sortowanie aktywnych i historycznych wypożyczeń

---

### 🌐 REST API

Pełne CRUD API dla:
- Assets
- Categories
- Persons
- Offices
- Rooms
- Desks
- Loans

Logika biznesowa obowiązuje również w warstwie API.

Endpoint główny:
