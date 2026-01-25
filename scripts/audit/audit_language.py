import os
import sys
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

# Add the parent directory to sys.path to allow imports from backend
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

load_dotenv()

# Common terms identification
ENGLISH_TERMS = {
    'user', 'users', 'account', 'profile', 'role', 'permission', 'auth',
    'publication', 'publications', 'author', 'authors', 'researcher', 'researchers',
    'project', 'projects', 'grant', 'funding', 'institution', 'department',
    'metric', 'metrics', 'stat', 'stats', 'data', 'file', 'files',
    'id', 'uuid', 'created', 'updated', 'at', 'by', 'name', 'title', 'description',
    'status', 'type', 'category', 'tag', 'tags', 'slug', 'url', 'link',
    'email', 'password', 'hash', 'salt', 'token', 'session', 'log', 'logs',
    'audit', 'history', 'version', 'revision', 'content', 'text', 'body',
    'summary', 'abstract', 'keyword', 'keywords', 'doi', 'isbn', 'issn',
    'year', 'date', 'month', 'day', 'time', 'score', 'value', 'count',
    'total', 'active', 'inactive', 'enable', 'disable', 'is', 'has',
    'first', 'last', 'full', 'short', 'long', 'image', 'photo', 'avatar',
    'group', 'member', 'members', 'team', 'teams', 'client', 'product',
    'service', 'order', 'invoice', 'payment', 'address', 'city', 'country',
    'phone', 'mobile', 'detail', 'details', 'config', 'setting', 'settings',
    'meta', 'metadata', 'citation', 'citations', 'reference', 'references',
    'journal', 'conference', 'book', 'chapter', 'sync', 'source', 'external',
    'original', 'translated', 'language', 'locale', 'translation'
}

SPANISH_TERMS = {
    'usuario', 'usuarios', 'cuenta', 'perfil', 'rol', 'permiso', 'autenticacion',
    'publicacion', 'publicaciones', 'autor', 'autores', 'investigador', 'investigadores',
    'proyecto', 'proyectos', 'fondo', 'financiamiento', 'institucion', 'departamento',
    'metrica', 'metricas', 'estadistica', 'estadisticas', 'dato', 'datos', 'archivo', 'archivos',
    'identificador', 'creado', 'actualizado', 'en', 'por', 'nombre', 'titulo', 'descripcion',
    'estado', 'tipo', 'categoria', 'etiqueta', 'etiquetas', 'enlace', 'correo', 'contrasena',
    'clave', 'ficha', 'registro', 'historial', 'version', 'revision', 'contenido', 'texto', 'cuerpo',
    'resumen', 'abstracto', 'palabra', 'palabras', 'clave', 'ano', 'fecha', 'mes', 'dia', 'hora',
    'puntaje', 'valor', 'conteo', 'total', 'activo', 'inactivo', 'habilitar', 'deshabilitar', 'es', 'tiene',
    'primer', 'ultimo', 'completo', 'corto', 'largo', 'imagen', 'foto', 'avatar',
    'grupo', 'miembro', 'miembros', 'equipo', 'equipos', 'cliente', 'producto',
    'servicio', 'orden', 'factura', 'pago', 'direccion', 'ciudad', 'pais',
    'telefono', 'celular', 'detalle', 'detalles', 'configuracion', 'ajuste', 'ajustes',
    'cita', 'citas', 'referencia', 'referencias', 'revista', 'conferencia', 'libro', 'capitulo',
    'sincronizacion', 'fuente', 'externo', 'original', 'traducido', 'idioma', 'traduccion'
}

def classify_term(term):
    """Classify a single term as English, Spanish, or Unknown."""
    # Normalize
    term = term.lower()
    
    # Direct match
    if term in ENGLISH_TERMS:
        return 'english'
    if term in SPANISH_TERMS:
        return 'spanish'
    
    # Check for plurals (naive)
    if term.endswith('s'):
        singular = term[:-1]
        if singular in ENGLISH_TERMS:
            return 'english'
        if singular in SPANISH_TERMS:
            return 'spanish'
            
    return 'unknown'

def classify_name(name):
    """Classify a table or column name (snake_case) based on its components."""
    parts = name.split('_')
    languages = set()
    
    for part in parts:
        if part.isdigit() or len(part) < 2: # Skip numbers and single letters
            continue
        lang = classify_term(part)
        languages.add(lang)
        
    if 'spanish' in languages and 'english' in languages:
        return 'MIXED'
    if 'spanish' in languages:
        return 'SPANISH'
    if 'english' in languages:
        return 'ENGLISH'
    
    return 'UNKNOWN' # Only unknown terms found


def audit_language():
    print("🌍 AUDITORIA DE IDIOMA DE BASE DE DATOS")
    print("========================================")
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ ERROR: DATABASE_URL no encontrada en .env")
        return

    try:
        engine = create_engine(db_url)
        insp = inspect(engine)
        
        tables = insp.get_table_names()
        
        report = {
            'ENGLISH': [],
            'SPANISH': [],
            'MIXED': [],
            'UNKNOWN': []
        }
        
        col_report = {
            'ENGLISH': 0,
            'SPANISH': 0,
            'MIXED': 0,
            'UNKNOWN': 0
        }
        
        print(f"Analizando {len(tables)} tablas...\n")
        
        for table in tables:
            if table == 'alembic_version':
                continue
                
            table_lang = classify_name(table)
            
            columns = insp.get_columns(table)
            col_details = []
            
            for col in columns:
                col_name = col['name']
                col_lang = classify_name(col_name)
                col_report[col_lang] += 1
                col_details.append((col_name, col_lang))
            
            # Determine overall table health regarding language
            table_entry = {
                'name': table,
                'lang': table_lang,
                'columns': col_details
            }
            
            report[table_lang].append(table_entry)

        # Print Report
        for lang in ['SPANISH', 'MIXED', 'UNKNOWN', 'ENGLISH']:
            items = report[lang]
            if not items:
                continue
                
            print(f"--- {lang} ({len(items)}) ---")
            for item in items:
                print(f"  📂 Tabla: {item['name']}")
                
                # Check for column inconsistencies
                bad_cols = [c for c in item['columns'] if c[1] != lang and c[1] != 'UNKNOWN' and lang != 'MIXED']
                
                if bad_cols:
                    print(f"     ⚠️  Columnas discordantes:")
                    for c_name, c_lang in bad_cols:
                         print(f"       - {c_name} ({c_lang})")
                elif lang == 'MIXED':
                     print(f"     ⚠️  Columnas:")
                     for c_name, c_lang in item['columns']:
                         print(f"       - {c_name} ({c_lang})")
            print("")

        print("📊 RESUMEN FINAL DE COLUMNAS")
        print(f"   🇺🇸 English: {col_report['ENGLISH']}")
        print(f"   🇪🇸 Spanish: {col_report['SPANISH']}")
        print(f"   🔀 Mixed:   {col_report['MIXED']}")
        print(f"   ❓ Unknown: {col_report['UNKNOWN']}")

    except Exception as e:
        print(f"\n❌ ERROR DE EJECUCIÓN: {e}")

if __name__ == "__main__":
    audit_language()
