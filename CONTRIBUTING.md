# Flujo de trabajo

## Preparar el entorno (Windows)
```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements-dev.txt
pre-commit install            &:: opcional: lint automático antes de cada commit
```

## Ciclo de un cambio
1. Crea un issue (o toma uno) que describa el problema y los criterios de aceptación.
2. Crea una rama desde `main`: `feat/modificadores-con-precio`, `fix/redondeo-descuento`.
3. Programa el cambio **con su prueba** en `tests/`. Para un bug, primero escribe la prueba que falla.
4. Verifica localmente:
   ```bat
   ruff check . && ruff format --check .
   python -m pytest
   python -m app.main --browser     &:: prueba manual
   ```
5. Commit con [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/):
   `feat(pos): agrega modificadores con precio`, `fix(inventario): corrige costo promedio con stock negativo`.
6. Abre un Pull Request hacia `main`; la CI (lint + pruebas en Ubuntu y Windows) debe pasar.
7. Merge con *squash* y borra la rama.

## Versiones y entregas
Cada Pull Request que se fusiona a `main` sube la versión ([versionado semántico](https://semver.org/lang/es/)) para
conservar un historial de cambios:

| Tipo de cambio | Sube | Ejemplo |
|---|---|---|
| Funcionalidad nueva (`feat`) | **minor** | 1.1.0 → 1.2.0 |
| Corrección, documentación, pruebas, build/CI (`fix`, `docs`, `test`, `build`, `ci`) | **patch** | 1.2.0 → 1.2.1 |
| Cambio que rompe compatibilidad (datos, API) | **major** | 1.2.1 → 2.0.0 |

1. En el PR: actualiza `__version__` en `app/__init__.py`, `version` en `pyproject.toml`, el `AppVersion` por defecto de
   `packaging/installer.iss` y escribe la entrada en `CHANGELOG.md` (`## [X.Y.Z] - AAAA-MM-DD`, más el enlace al final).
   La prueba `tests/test_version.py` falla si algo de esto no coincide. Los commits intermedios de un mismo PR no suben versión.
2. Después del merge, desde `main`: `git tag vX.Y.Z && git push origin vX.Y.Z`
3. El workflow **Build Windows** compila el `.exe`, corre una prueba de humo, genera el instalador y lo
   publica en *Releases*.

## Cambios a la base de datos
- El esquema vive en `app/db.py`. Todo cambio debe ser **idempotente** (`CREATE ... IF NOT EXISTS`,
  `ALTER TABLE` protegido revisando `PRAGMA table_info`) y subir `SCHEMA_VERSION`.
- Nunca eliminar columnas con datos de clientes; documentar en `docs/modelo-de-datos.md`.

## Trabajar con Claude Code
- `CLAUDE.md` contiene el contexto y las reglas del proyecto; mantenlo actualizado cuando cambie la arquitectura.
- Pide cambios pequeños y verificables ("agrega X con su prueba"), revisa el diff y deja que corra `pytest`.
