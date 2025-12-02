---
description: Explicación detallada de técnicas de matching para Fase 1
---

# 🔍 Fase 1: Estrategias de Matching Detalladas

## 📊 Contexto: ¿Qué Datos Tenemos?

Según tu modelo de datos actual:

```python
# Tabla: publicaciones
- titulo: "Cancer research in Chile..."
- autores: "García, J., Pérez, M., Smith, A."  # ⚠️ Texto plano
- url_origen: "https://doi.org/10.1234/example"
- contenido_texto: "Full text of the paper..."

# Tabla: academic_members
- full_name: "Juan García López"
- email: "jgarcia@uc.cl"
- institution: "Universidad Católica de Chile"
```

**Problema:** Necesitamos vincular "García, J." (en publicación) con "Juan García López" (en BD)

---

## 🎯 Estrategia Multi-Nivel de Matching

### **NIVEL 1: Extracción de DOI y Consulta a Crossref** 🟢 ALTA CONFIANZA

#### Paso 1.1: Extraer DOI de la URL

**Técnica: REGEX**

```python
import re

def extract_doi(url: str) -> Optional[str]:
    """
    Extrae DOI de URLs comunes
    
    Ejemplos:
    - https://doi.org/10.1234/example → 10.1234/example
    - https://dx.doi.org/10.1038/s41586-020-2012-7 → 10.1038/s41586-020-2012-7
    - https://www.nature.com/articles/s41586-020-2012-7 → 10.1038/s41586-020-2012-7
    """
    
    # Patrón 1: DOI directo en URL
    pattern1 = r'doi\.org/(10\.\d{4,}/[^\s]+)'
    match = re.search(pattern1, url)
    if match:
        return match.group(1)
    
    # Patrón 2: DOI en path de journal
    pattern2 = r'(10\.\d{4,}/[a-zA-Z0-9\.\-\_/]+)'
    match = re.search(pattern2, url)
    if match:
        return match.group(1)
    
    return None

# Ejemplos:
extract_doi("https://doi.org/10.1038/s41586-020-2012-7")
# → "10.1038/s41586-020-2012-7"

extract_doi("https://pubmed.ncbi.nlm.nih.gov/32350462/")
# → None (necesitaríamos consultar PubMed API)
```

**Ventajas:**
- ✅ Muy rápido (no requiere API)
- ✅ Alta precisión para URLs estándar
- ✅ No tiene límites de rate

**Desventajas:**
- ⚠️ Solo funciona si la URL contiene el DOI
- ⚠️ Algunos journals usan URLs propietarias

---

#### Paso 1.2: Consultar Crossref API

**Técnica: API REST (Sin autenticación)**

```python
import requests
from typing import List, Dict

def get_publication_metadata(doi: str) -> Dict:
    """
    Obtiene metadata completa de Crossref
    
    API: https://api.crossref.org/works/{doi}
    Rate Limit: Gratis, pero recomiendan max 50 req/seg
    """
    
    url = f"https://api.crossref.org/works/{doi}"
    headers = {
        "User-Agent": "CECAN-Platform/1.0 (mailto:admin@cecan.cl)"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()['message']
        
        # Extraer información relevante
        return {
            'title': data.get('title', [''])[0],
            'doi': doi,
            'authors': [
                {
                    'given': author.get('given', ''),
                    'family': author.get('family', ''),
                    'full_name': f"{author.get('given', '')} {author.get('family', '')}".strip(),
                    'orcid': author.get('ORCID', '').replace('http://orcid.org/', ''),
                    'affiliation': author.get('affiliation', [])
                }
                for author in data.get('author', [])
            ],
            'published_date': data.get('published', {}).get('date-parts', [[None]])[0],
            'journal': data.get('container-title', [''])[0],
            'abstract': data.get('abstract', None)
        }
    
    return None

# Ejemplo de respuesta:
{
    'title': 'Cancer immunotherapy in Chile',
    'doi': '10.1234/example',
    'authors': [
        {
            'given': 'Juan',
            'family': 'García',
            'full_name': 'Juan García',
            'orcid': '0000-0002-1234-5678',  # ⭐ ESTO ES LO QUE QUEREMOS
            'affiliation': [
                {'name': 'Universidad Católica de Chile'}
            ]
        },
        {
            'given': 'María',
            'family': 'Pérez',
            'full_name': 'María Pérez',
            'orcid': '',  # ⚠️ No todos tienen ORCID
            'affiliation': []
        }
    ]
}
```

**Ventajas:**
- ✅ Datos verificados por el journal
- ✅ Incluye ORCIDs cuando están disponibles
- ✅ Gratis, sin autenticación
- ✅ Incluye afiliaciones institucionales

**Desventajas:**
- ⚠️ No todos los autores tienen ORCID en Crossref (~40-60% coverage)
- ⚠️ Requiere conexión a internet
- ⚠️ Rate limits (pero generosos)

---

### **NIVEL 2: Matching de Nombres** 🟡 CONFIANZA MEDIA

Ahora tenemos:
- **De Crossref:** `"Juan García"` (nombre normalizado)
- **De nuestra BD:** `"Juan García López"` (nombre completo)

#### Técnica 2.1: Fuzzy String Matching

**Librería: `fuzzywuzzy` o `rapidfuzz`**

```python
from rapidfuzz import fuzz, process

def fuzzy_match_author(crossref_author: str, db_researchers: List[str]) -> Dict:
    """
    Encuentra el investigador más similar usando fuzzy matching
    
    Algoritmos disponibles:
    1. ratio: Similitud básica (Levenshtein)
    2. partial_ratio: Coincidencia parcial
    3. token_sort_ratio: Ignora orden de palabras
    4. token_set_ratio: Ignora palabras duplicadas
    """
    
    # Normalizar nombres
    crossref_normalized = normalize_name(crossref_author)
    
    # Buscar mejor match
    best_match = process.extractOne(
        crossref_normalized,
        db_researchers,
        scorer=fuzz.token_sort_ratio  # Ignora orden: "García Juan" = "Juan García"
    )
    
    if best_match:
        matched_name, score, index = best_match
        return {
            'matched_name': matched_name,
            'confidence': score / 100,  # 0.0 - 1.0
            'method': 'fuzzy_token_sort'
        }
    
    return None

def normalize_name(name: str) -> str:
    """Normaliza nombres para mejor matching"""
    import unicodedata
    
    # Remover acentos
    name = unicodedata.normalize('NFKD', name)
    name = name.encode('ASCII', 'ignore').decode('utf-8')
    
    # Lowercase y remover caracteres especiales
    name = re.sub(r'[^a-z\s]', '', name.lower())
    
    # Remover espacios extra
    name = ' '.join(name.split())
    
    return name

# Ejemplos:
normalize_name("García López, Juan")  # → "garcia lopez juan"
normalize_name("Juan García-López")   # → "juan garcia lopez"

fuzzy_match_author(
    "Juan García",  # De Crossref
    ["Juan García López", "María Pérez Silva", "Pedro González"]  # De BD
)
# → {'matched_name': 'Juan García López', 'confidence': 0.85, 'method': 'fuzzy_token_sort'}
```

**Scores de Confianza:**
- **95-100%:** Match casi exacto → Auto-asignar
- **85-94%:** Alta probabilidad → Auto-asignar con log
- **70-84%:** Posible match → Revisión manual
- **< 70%:** Descartado

---

#### Técnica 2.2: Matching por Iniciales + Apellido

**Técnica: REGEX + Lógica**

```python
def match_by_initials(crossref_author: str, db_name: str) -> float:
    """
    Compara usando patrón común en papers: "García, J."
    
    Ejemplos:
    - "García, J." matches "Juan García López" ✅
    - "García, J.A." matches "Juan Antonio García" ✅
    - "Smith, A." matches "Andrew Smith" ✅
    """
    
    # Extraer apellido e iniciales del autor de Crossref
    pattern = r'([A-Za-zÁ-ú\-]+),\s*([A-Z]\.?(?:[A-Z]\.?)?)'
    match = re.match(pattern, crossref_author)
    
    if not match:
        return 0.0
    
    last_name, initials = match.groups()
    initials = initials.replace('.', '').upper()
    
    # Normalizar nombre de BD
    db_normalized = normalize_name(db_name)
    db_parts = db_normalized.split()
    
    # Buscar apellido en nombre de BD
    last_name_normalized = normalize_name(last_name)
    if last_name_normalized not in db_parts:
        return 0.0
    
    # Verificar iniciales
    db_initials = ''.join([part[0].upper() for part in db_parts if part != last_name_normalized])
    
    if initials == db_initials[:len(initials)]:
        return 0.9  # Alta confianza
    elif initials[0] == db_initials[0]:
        return 0.7  # Solo primera inicial coincide
    
    return 0.0

# Ejemplos:
match_by_initials("García, J.", "Juan García López")  # → 0.9
match_by_initials("García, J.A.", "Juan Antonio García")  # → 0.9
match_by_initials("García, J.", "María García")  # → 0.0 (inicial no coincide)
```

---

### **NIVEL 3: Validación Contextual** 🔵 REFINAMIENTO

#### Técnica 3.1: Validación por Afiliación

```python
def validate_by_affiliation(crossref_author: Dict, db_researcher: Dict) -> float:
    """
    Aumenta confianza si la afiliación coincide
    """
    
    affiliations = crossref_author.get('affiliation', [])
    db_institution = db_researcher.get('institution', '')
    
    # Palabras clave de tu institución
    keywords = ['católica', 'chile', 'uc', 'pontificia']
    
    for aff in affiliations:
        aff_name = normalize_name(aff.get('name', ''))
        
        # Si la afiliación menciona tu universidad
        if any(keyword in aff_name for keyword in keywords):
            # Y el investigador es de tu universidad
            if any(keyword in normalize_name(db_institution) for keyword in keywords):
                return 0.95  # Muy alta confianza
    
    return 0.5  # Sin información de afiliación

# Ejemplo:
crossref_author = {
    'full_name': 'Juan García',
    'affiliation': [{'name': 'Pontificia Universidad Católica de Chile'}]
}

db_researcher = {
    'full_name': 'Juan García López',
    'institution': 'Universidad Católica de Chile'
}

validate_by_affiliation(crossref_author, db_researcher)  # → 0.95
```

---

#### Técnica 3.2: Validación por Co-autores

```python
def validate_by_coauthors(publication_authors: List[str], researcher_id: int, db) -> float:
    """
    Si otros autores del paper ya están en nuestra BD,
    aumenta la confianza del match
    """
    
    # Obtener publicaciones previas del investigador
    previous_pubs = db.get_researcher_publications(researcher_id)
    previous_coauthors = set()
    
    for pub in previous_pubs:
        previous_coauthors.update(pub['authors'])
    
    # Contar cuántos autores del paper actual ya colaboraron antes
    current_authors = set(publication_authors)
    overlap = len(current_authors.intersection(previous_coauthors))
    
    if overlap >= 2:
        return 0.9  # Ha publicado con 2+ autores de este paper antes
    elif overlap == 1:
        return 0.7  # Ha publicado con 1 autor antes
    
    return 0.5  # Sin co-autores conocidos

# Ejemplo:
# Paper actual: ["García, J.", "Pérez, M.", "Smith, A."]
# Papers previos de Juan García: incluyen a "Pérez, M." y "González, P."
# → overlap = 1 → confidence = 0.7
```

---

## 🎯 Algoritmo Completo de Matching

```python
class AuthorMatcher:
    def __init__(self, db):
        self.db = db
        self.researchers = db.get_all_researchers()
    
    def match_publication(self, doi: str) -> List[Dict]:
        """
        Pipeline completo de matching
        """
        
        # PASO 1: Obtener metadata de Crossref
        metadata = get_publication_metadata(doi)
        if not metadata:
            return []
        
        matches = []
        
        # PASO 2: Para cada autor en el paper
        for crossref_author in metadata['authors']:
            
            # PASO 2.1: ¿Tiene ORCID directo?
            if crossref_author['orcid']:
                # Buscar en BD por ORCID (si ya lo tenemos)
                db_match = self.db.find_by_orcid(crossref_author['orcid'])
                if db_match:
                    matches.append({
                        'researcher_id': db_match['id'],
                        'orcid': crossref_author['orcid'],
                        'confidence': 1.0,
                        'method': 'orcid_exact'
                    })
                    continue
                else:
                    # Nuevo ORCID descubierto
                    matches.append({
                        'researcher_id': None,
                        'orcid': crossref_author['orcid'],
                        'full_name': crossref_author['full_name'],
                        'confidence': 0.95,
                        'method': 'orcid_new',
                        'action': 'create_or_link'
                    })
                    continue
            
            # PASO 2.2: Fuzzy matching por nombre
            fuzzy_result = fuzzy_match_author(
                crossref_author['full_name'],
                [r['full_name'] for r in self.researchers]
            )
            
            if not fuzzy_result or fuzzy_result['confidence'] < 0.7:
                continue  # Skip, confianza muy baja
            
            # PASO 2.3: Validaciones contextuales
            researcher_id = self._get_researcher_id(fuzzy_result['matched_name'])
            researcher = self.db.get_researcher(researcher_id)
            
            # Ajustar confianza con afiliación
            aff_score = validate_by_affiliation(crossref_author, researcher)
            
            # Ajustar confianza con co-autores
            coauthor_score = validate_by_coauthors(
                [a['full_name'] for a in metadata['authors']],
                researcher_id,
                self.db
            )
            
            # Combinar scores (promedio ponderado)
            final_confidence = (
                fuzzy_result['confidence'] * 0.5 +
                aff_score * 0.3 +
                coauthor_score * 0.2
            )
            
            matches.append({
                'researcher_id': researcher_id,
                'orcid': None,  # No tenía ORCID en Crossref
                'confidence': final_confidence,
                'method': 'fuzzy_validated',
                'details': {
                    'fuzzy_score': fuzzy_result['confidence'],
                    'affiliation_score': aff_score,
                    'coauthor_score': coauthor_score
                }
            })
        
        return matches
```

---

## 📊 Resumen de Técnicas

| Técnica | Uso | Confianza | Velocidad |
|---------|-----|-----------|-----------|
| **REGEX (DOI)** | Extraer DOI de URL | N/A | ⚡⚡⚡ Instantáneo |
| **Crossref API** | Obtener metadata | Alta | ⚡⚡ ~200ms/request |
| **ORCID Exacto** | Match directo | 100% | ⚡⚡⚡ Instantáneo |
| **Fuzzy Matching** | Similitud de nombres | 70-95% | ⚡⚡ Rápido |
| **Iniciales + Apellido** | Formato "García, J." | 70-90% | ⚡⚡⚡ Instantáneo |
| **Validación Afiliación** | Confirmar institución | +10-20% | ⚡⚡⚡ Instantáneo |
| **Validación Co-autores** | Red de colaboración | +10-20% | ⚡ Medio |

---

## 🚦 Estrategia de Decisión

```python
def decide_action(match: Dict) -> str:
    """
    Decide qué hacer con cada match
    """
    
    confidence = match['confidence']
    
    if confidence >= 0.95:
        return "AUTO_ASSIGN"  # Asignar automáticamente
    
    elif confidence >= 0.80:
        return "AUTO_ASSIGN_WITH_LOG"  # Asignar pero registrar para auditoría
    
    elif confidence >= 0.65:
        return "MANUAL_REVIEW"  # Marcar para revisión humana
    
    else:
        return "SKIP"  # Descartar
```

---

## 💡 Ventajas de Este Enfoque

1. **Multi-nivel:** Combina varias técnicas para máxima precisión
2. **Transparente:** Cada match tiene un score de confianza explicable
3. **Auditable:** Registra el método usado para cada asignación
4. **Escalable:** Puede procesar miles de publicaciones
5. **Robusto:** Maneja casos edge (nombres con acentos, iniciales, etc.)

---

## 🎯 Respuesta a Tu Pregunta

**¿Usamos REGEX o Fuzzy Matching?**

**Respuesta: AMBOS, en diferentes etapas:**

1. **REGEX** → Para extraer DOIs de URLs (rápido, preciso)
2. **API REST** → Para obtener metadata de Crossref (datos verificados)
3. **ORCID Exacto** → Si está disponible en Crossref (100% confianza)
4. **Fuzzy Matching** → Para vincular nombres cuando no hay ORCID (70-95% confianza)
5. **Validación Contextual** → Para refinar la confianza (+10-20%)

**No es uno u otro, es un pipeline que usa la técnica apropiada en cada paso.**

---

**¿Te parece sensato este enfoque? ¿Quieres que empecemos a implementarlo?** 🚀
