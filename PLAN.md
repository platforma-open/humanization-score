# Humanization Score Block — Engineering Plan

Инженерный план реализации блока `humanization-score`. Биология сведена к минимуму: с точки зрения кода блок — это `f(amino_acid_sequence: string) → float`, обёрнутый в стандартный пайплайн-юнит платформы.

Источник требований: `Antibody Humanization Score.md`.

## Workflow

- **Все задачи выполняются через сабагентов** (Agent tool). Главный поток оркеструет и проверяет результат, сами действия (клон репо, копирование файлов, правки кода, сборка) делегируются.
- После выполнения каждого шага плана его статус и краткий отчёт фиксируются в этом файле в разделе **Execution log** в конце.
- Каждой задаче в плане соответствует один сабагент-вызов; если задача крупная — несколько последовательных или параллельных.

---

## 0. Pre-flight (до начала кода)

- [ ] Уточнить, где живёт блок: в этом репо или в монорепе платформы рядом с `blocks/antibody-sequence-liabilities/`.
- [ ] Получить доступ к репо-прецедентам (см. §2). Без них реализовать корректные PColumn-аннотации нельзя.
- [ ] Получить тестовые датасеты для трёх модальностей: VHH, mAb, scFv.
- [ ] Получить «эталонную» панель из заведомо человеческих и заведомо не-человеческих последовательностей для acceptance-теста (§8).

---

## 1. Контракт блока

### Вход
- Существующая PColumn с аминокислотными последовательностями антител (та же форма, что у `antibody-sequence-liabilities`).
- Поддерживаемые модальности: **VHH, mAb, scFv**.

### Выход
- Одна PColumn на каждую скорённую цепь (heavy / light / обе — зависит от модальности).
- `value type: Float`.
- Шкала: больше = более «человечно». Если выбранный инструмент даёт обратное — инвертируем.
- Рекомендуемая нормализация: 0–100 (или 0–1), чтобы шкала была независима от метода (метод может смениться в v2).
- Аннотация `pl7.app/isScore: "true"` — ставится **только** если у выбранного метода есть опубликованная валидация против иммуногенности. Решение — за имплементатором, фиксируется в `description.md`. ⚠️ **Текущее состояние**: `isScore: "true"` уже выставлен в обоих tengo-шаблонах (для участия в Lead Selection), но обоснование в `description.md` ещё не зафиксировано — open question формально не закрыт.

### Что блок НЕ делает (out of scope)
- Per-residue скор (какие позиции тянут скор вниз).
- Предложения мутаций (back-mutation к человеческой germline).
- Параллельный скоринг несколькими методами.
- Hard-filter в Lead Selection (только ranking).

---

## 2. Файлы-прецеденты, которые нужно прочитать ПЕРЕД кодом

| Что | Где | Зачем |
|-----|-----|-------|
| Структура блока-скоринга | `blocks/antibody-sequence-liabilities/` | Копируем как скелет |
| Конвенции PColumn (isScore, defaultCutoff и т.п.) | `docs/text/work/projects/sequence-liability-fixability-scoring/pcolumn-spec.md` | Чтобы Lead Selection нашёл колонку |
| Discovery колонок в Lead Selection | `blocks/antibody-tcr-lead-selection/model/src/util.ts` | Понять, какие аннотации блок ищет |

Эти файлы — единственный надёжный источник правды по формату. Без их чтения дальше не двигаться.

---

## 3. Выбор движка скоринга

Это самостоятельная инженерная подзадача. Чисто технические критерии:

- **Лицензия**: open source, permissive (требуется для редистрибуции платформы).
- **Footprint**: размер контейнера, веса модели, рантайм-зависимости (Python/PyTorch/прочее).
- **Производительность**: per-sequence cost → определяет, влезает ли полный репертуар или только pre-filtered панель.
- **Модальности**: должен покрывать VHH, mAb, scFv (либо обвязка блока сводит вход к поддерживаемому формату).
- **Валидация**: наличие опубликованной валидации → влияет на `isScore`.
- **Выход**: одно число; method-specific шкалу ремасштабируем.

Кандидаты для рисёрча (не финальный список): BioPhi/OASis, AbNatiV, Hu-mAb, IgReconstruct.

**Артефакт этого этапа**: короткий decision-doc внутри `description.md` — что выбрано, какие альтернативы рассмотрены, почему.

> ✅ **Движок выбран**: `promb` (пакет `promb>=1.0.2`), БД `human-oas` — OASis-style скор: доля 9-меров последовательности, встречающихся в человеческих репертуарах, ремасштаб 0..100, больше = человечнее. ⚠️ decision-doc в `description.md` ещё НЕ написан (см. §9), альтернативы формально не задокументированы.

---

## 4. Скаффолд блока

Источник: `git@github.com:platforma-open/antibody-sequence-liabilities.git`. Прецедент явно назван в брифе.

- [ ] **(сабагент)** Склонировать `antibody-sequence-liabilities` во временную директорию, прочитать структуру.
- [ ] **(сабагент)** Заменить текущий «чужой» скафолд (он скопирован с `antibody-tcr-lead-selection`, видно по `block/package.json:meta.title` и URL) на структуру `antibody-sequence-liabilities`.
- [ ] **(сабагент)** Сохранить только: `.git/`, `Antibody Humanization Score.md`, `PLAN.md`, `README.md` (если он не пустой). Всё остальное (включая `node_modules`, build-артефакты) подлежит замене / регенерации.
- [ ] **(сабагент)** Переименовать имена пакетов: `antibody-sequence-liabilities` → `humanization-score` во всех `package.json`, `pnpm-workspace.yaml`, ссылках между воркспейсами.
- [ ] **(сабагент)** Обновить `block/package.json:meta` (title, description, url, docs) под humanization-score; конкретные тексты — placeholder, финализируются в §9.
- [ ] Использовать **BlockModelV3** (текущая конвенция; должно унаследоваться от прецедента).
- [ ] Не коммитить — главный поток смотрит diff и решает.

---

## 5. Контейнеризация выбранного инструмента

- [ ] Dockerfile для выбранного скорера: системные либы, рантайм, веса модели.
- [ ] Зафиксировать версии (модель + код инструмента) для воспроизводимости.
- [ ] CLI-обёртка: `stdin/stdout` или `--input file --output file`, чтобы workflow дёргал детерминированно.
- [ ] Замерить per-sequence latency и throughput на репрезентативной выборке. Записать в `description.md` потолок практически разумного входа.

---

## 6. Workflow (оркестрация)

- [x] Чтение входной PColumn с последовательностями.
- [x] Итерация по строкам (или батчинг, если инструмент поддерживает) → вызов скорера (`humanness-calc-script`, `main.py` / `peptide_main.py`).
- [~] Сбор результата → запись output PColumn(ов):
  - ⚠️ Сейчас **одна** колонка `humanness_score` на клонотип: все колонки `* aa` конкатенируются и скорятся одним числом. Раздельных heavy/light колонок НЕТ — пересмотреть, нужна ли per-chain детализация.
  - Для VHH/peptide одна цепь — покрыто.
- [x] Нормализация шкалы 0..100 (см. §1).
- [x] Навешивание аннотаций по `pcolumn-spec.md` (`pl7.app/humannessScore`, `isScore: "true"`, `rankingOrder: "decreasing"`, `score/method`).

---

## 7. Интеграция с Lead Selection

- [ ] Проверить, как `blocks/antibody-tcr-lead-selection/model/src/util.ts` обнаруживает скоринговые колонки. ⚠️ НЕ подтверждено, что выставленные аннотации совпадают с тем, что ищет util.ts.
- [x] Навесить на выходную PColumn аннотации для автоподхвата как **default ranking criterion** (`isScore: "true"` + `score/rankingOrder: "decreasing"`).
- [x] **Код Lead Selection не трогаем** — соблюдено (изменений в нём нет).
- [ ] Проверить интеграцию сквозным прогоном. ⚠️ НЕ сделано.

---

## 8. Тесты и acceptance

- [ ] `pnpm build` зелёный.
- [ ] Integration tests блока проходят.
- [ ] Прогон на сэмпле для каждой модальности: VHH, mAb, scFv.
- [ ] **Sanity-тест**: на смешанной панели «известно человеческие» vs «известно не-человеческие» → средний скор у человеческих заметно выше. Это финальный acceptance, который доказывает, что обвязка не сломала смысл скора.
- [ ] Прогон через Lead Selection: колонка появилась, ранжирование работает.

Маппинг на Success Criteria брифа:

| Критерий из брифа | Покрывается шагом |
|---|---|
| Block builds, installs, runs | §4, §5, §8 |
| Produces humanness score PColumn per chain | §6 |
| Wired into Lead Selection as default ranking criterion | §7 |
| Runs on VHH, mAb, scFv | §6, §8 |
| Human > non-human on mixed panel | §8 (sanity-тест) |
| `description.md` documents method, license, scale | §3, §9 |
| `pnpm build` + integration tests | §8 |

---

## 9. Документация

`description.md` в блоке должен содержать:

- Выбранный метод и его источник/версию.
- Лицензию.
- Шкалу скора (диапазон, ориентация: больше = лучше).
- Покрытие модальностей.
- Бенчмарк производительности → практический потолок размера входа.
- Решение по `isScore` и обоснование (есть валидация / нет валидации).
- Рассмотренные альтернативы (коротко, почему отвергнуты).

---

## 10. Порядок выполнения

1. §0 — pre-flight, разблокировать доступы.
2. §2 — прочитать три файла-прецедента.
3. §3 — выбрать движок скоринга.
4. §4 — скаффолд блока.
5. §5 — контейнер + CLI-обёртка инструмента.
6. §6 — workflow + PColumn IO.
7. §7 — навесить аннотации, проверить discovery в Lead Selection.
8. §8 — прогон тестов, sanity-чек.
9. §9 — финализировать `description.md`.

---

## Открытые вопросы (наследуются из брифа)

- `isScore: "true"` — решается после выбора метода в §3.
- Потолок размера входа — измеряется в §5, фиксируется в §9.
- Финальная нормализация шкалы — решается в §6 (рекомендация: 0–100).

---

## Execution log

Хронология выполнения. Каждая запись: дата, шаг плана, кто делал (агент / основной поток), краткий итог.

| Дата | Шаг | Исполнитель | Итог |
|------|-----|-------------|------|
| 2026-05-26 | §4 копирование скафолда из `antibody-sequence-liabilities` | сабагент | Готово. Источник: коммит `ff07500` от 2026-05-26. Старый скафолд (от `antibody-tcr-lead-selection`) удалён, заменён на `antibody-sequence-liabilities`. Сохранены `.git/`, `Antibody Humanization Score.md`, `PLAN.md`, `README.md`, `.pnpm-store/`. Имена пакетов переименованы (`antibody-sequence-liabilities` → `humanization-score`). Директория `liabilities-calc-script/` → `humanness-calc-script/`. Обновлены `block.meta.title` = "Humanization Score", `meta.description` = placeholder, `meta.url`/`meta.docs` указывают на humanization-score. `git status`: 97 изменений, ничего не закоммичено. `pnpm install` не запускался. |
| 2026-05-26 | Шаг A: `pnpm build` зелёный | сабагент | Build OK с нуля, правок не потребовалось. Собраны 9 задач: model, ui, workflow (tengo), humanness-calc-script, block-pack. WARN'ы: `${NPMJS_TOKEN}` в `.npmrc` (только для publish), vite chunk-size в `ui/dist` (preexisting). |
| 2026-05-26 | Шаг B: stub-логика humanness | сабагент | Build OK + Python tests 6/6 зелёные. Stub-функция: `100 * (доля стандартных AA) / len(seq)`, диапазон 0..100, детерминированная. Выходной PColumn: одна колонка `humanness_score: Double` со спекой `pl7.app/humannessScore`, label "Humanness Score". Работает для clonotype и peptide веток. `pl7.app/isScore` НЕ выставлен (open question). Удалены `annotations.py`/`definitions.py`/`detection.py`/`scoring.py` из python-скрипта. 15 файлов изменено, ничего не закоммичено. |
| 2026-05-27 | §9 `description.md` + косметика | сабагенты | **§9**: `docs/description.md` переписан под humanness (метод promb/OASis, шкала 0..100, модальности, isScore, альтернативы). Verified: promb = MIT (© Merck), OAS = CC-BY 4.0, OASis-валидация (Prihoda et al., mAbs 2022). OPEN ITEMS: лицензия на bundled `human-oas` артефакт (нужен sign-off), бенчмарк не измерен (§5), per-sequence валидация не подтверждена. **Косметика**: `*-liabilities.tpl.tengo`→`*-humanness.tpl.tengo` (git mv + ссылки), все CHANGELOG'и очищены → 0.1.0, версии package.json → 0.1.0. `pnpm build` зелёный (9/9). Не закоммичено. |
| 2026-05-27 | §3 + §6 + §7: реальный скорер promb/OASis | (закоммичено: `975da7f`→`a09d386`) | Stub заменён на **promb / OASis** (`human-oas` DB): `humanness()` = доля 9-меров в человеческих репертуарах × 100. `main.py` (antibody, конкатенирует все `* aa` колонки) + `peptide_main.py` (переиспользует `humanness`). `requirements.txt`: `promb>=1.0.2`, `polars-lts-cpu==1.33.1`. Аннотации: `isScore: "true"`, `score/rankingOrder: "decreasing"`, `score/method: "promb / OASis (human-oas)"`. Model `index.ts` вычищен от liability dead-code (типы `CustomLiability` и args удалены, остался upgradeLegacy). UI вычищен от liability-контролов. **НЕ сделано**: decision-doc/`description.md` (§9, всё ещё про liabilities), sanity-тест человек vs не-человек (§8), сквозной прогон через Lead Selection (§7), сверка discovery в util.ts. |

### Шаг B — хвосты (от сабагента)

Это «недоделки» stub-этапа, которые НЕ блокируют запуск, но потребуют внимания:

1. ~~**Реальный скорер**~~ ✅ 2026-05-27: заменён на promb/OASis (`human-oas`) в `main.py` + `peptide_main.py`.
2. ~~**`pl7.app/isScore`**~~ ✅ 2026-05-27: выставлен `true` + `rankingOrder: "decreasing"` в обоих tengo-шаблонах. ⚠️ обоснование в `description.md` всё ещё не зафиксировано.
3. ~~**UI настроечная панель**~~ ✅ 2026-05-27: liability-контролы удалены, `MainPage.vue` сведён к таблице + customBlockLabel.
4. ~~**`model/src/index.ts`** dead-code~~ ✅ 2026-05-27: типы `CustomLiability`/liability-args удалены.
5. ~~**Tengo `*-liabilities.tpl.tengo`**~~ ✅ 2026-05-27: переименованы в `clonotype-humanness.tpl.tengo` / `peptide-humanness.tpl.tengo` (git mv), ссылки в `main.tpl.tengo` обновлены, `pnpm build` зелёный. (Внутренние var-имена типа `liabilitiesResultCalc` оставлены — не влияют на сборку.)
6. **Trace type** = `milaboratories.humanization-score` — если у Lead Selection есть привязка к `milaboratories.sequence-liabilities`, нужна сверка (см. §7).
7. **Workflow `bundleBuilder`** — собирает sequences + annotations + peptide-секвенции; `main.py` конкатенирует все `* aa` колонки. Пересмотреть, нужна ли per-chain (heavy/light) детализация вместо одного числа (см. §6).

### §4 — что осталось (нужны решения / не код)

Это «хвост» скафолд-этапа, фиксирую отдельно, чтобы не потерять:

1. **Логотипы** `logos/block-logo.png`, `logos/organization-logo.png` — сейчас от sequence-liabilities, нужны свои (или временно оставить, если ОК).
2. **`docs/description.md`** (`block.meta.longDescription`) — переписать под humanization score, финал в §9.
3. **`block.meta`**: финальные `title`, `description`, `docs`-URL, `tags`, `marketplaceRanking`. Сейчас placeholder.
4. ~~**`CHANGELOG.md`**~~ ✅ 2026-05-27: все CHANGELOG'и очищены от истории `antibody-sequence-liabilities`, сведены к одной записи `## 0.1.0 / Initial release`.
5. ~~**`version`**~~ ✅ 2026-05-27: версии во всех `package.json` сброшены к `0.1.0` (block/model/ui/workflow/humanness-calc-script).
6. ~~**`pnpm install`** — запустить для регенерации `pnpm-lock.yaml` под новые имена пакетов и установки `node_modules`.~~ ✅ 2026-05-26: выполнено, exit=0. Предупреждения: 6 deprecated subdependencies (transitive, неблокирующие) + peer-dep warnings.
7. **Бизнес-логика** — сейчас под капотом реализация sequence-liabilities (workflow tengo, model TS, UI, python-скрипт). Это будет вычищаться / переписываться на следующих шагах плана (§5–§7), а не здесь.
