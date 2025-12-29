import sqlite3
import csv
import io
import re
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import DB_PATH
except ImportError:
    DB_PATH = "cecan.db"

RAW_DATA = """c|TITULO|Investigador responsable|Principales (8)|Otros investigadores|otros WP involucrados|COLORECTAL|MAMA|EXPERIENCIA|CUELLO UTERINO|GASTRICO|VESICULA|PULMON|EPA|BIOMARCADORES|SOCIEDAD CIVIL
1|Modelamiento carga evitable|Paula Margozzini|Paula Margozzini|Pedro Zitko|2,4,5|X|X||X|X|X|X||||
1|Piloto preventivo|Lorena Rodríguez|Lorena Rodríguez|María Jesús Vega, Kenny Low, Paulina Espinoza, Javiera Soto|2,4|X|X|X|X|X|X|X||||
1|Desigualdades en sobrevida|Nicolás Silva|Paula Margozzini|Felipe Medina, Tania Alfaro, Felipe Quezada, Andrea Canals, Natalia Cuadros|4|X|X||X|X|X|X||||
1|Adherencia a prevencion|Solange Parra|Lorena Rodríguez|Solange Parra, Catalina Ramírez, Carlos Celis, Carla Villagrán||X|X||X||||||
1|Toxicos ambientales|María Teresa Muñoz|Lorena Rodríguez|Katherine Marcelain, Natalia Landeros, Liliana Zúñiga|3|X|X||X|X|X|X||X|
2|Capacidades de la red|Johanna Acevedo|Johanna Acevedo|Bruno Nervi|4,5|X|X|X|X|X|X|X||||
2|Trayectoria clinica|Johanna Acevedo|Johanna Acevedo|Bruno Nervi|4,5|X|X|X|X|X|X|X||||
2|Experiencia|Karla González|Johanna Acevedo|Sofía Bowen, Valentina Garrido, Felipe Elgueta|5||||X||||||
2|Prevencion cancer gastrico|Arnoldo Riquelme|Manuel Espinoza|Klaus Puschel, Laura Huidrobro|1,3,4,5||||||X|||X|
2|Control del cancer en atencion primaria|Klaus Puschel|Johanna Acevedo|Bruno Nervi, Jose Peña, Javiera Martínez, María Gabriela Soto, Andrea Rioseco, Mauricio Soto, Carolina Goic, Francisca Menoa, Eduardo Arenas, Marcela Faúndez, Paola Lanino, Matías González|1,4,5|X|X|X|X|X|X|X||||
2|Eleccion de lugar de fallecimeinto|Pedro Pérez Cruz|Bruno Nervi|Ofelia Leiva, Javiera Léniz|1,4||X||||||||
2|Impacto EPA|Silvia Palma|Bruno Nervi|Carolina Muñoz, Francisca Márquez, Camila Lucchini, Carolina Crocquevielle, Fernanda Farías, Camila Carrasco, Natalie Pinto, Javiera Hernández|4||||X|||||x|
2|IA y deteccion cancer pulmonar|Richard Weber|Bruno Nervi|Jose Peña, Sebastián Santana, Juan Carlos Opazo, Juan Cristóbal Morales, Natalie Pinto, Nicolas Barticevic, Rodrigo Villarroel, Diego Carrillo|3||||||||x||X|
2|Optimizacion trayectoria cancer de mama|César Sánchez|Bruno Nervi|Francisco Acevedo, Johanna Acevedo|3|||x|x||||||X|
2|Neuropatia por paclitaxel y fenotipo|Francisco Acevedo|Johanna Acevedo|César Sánchez|3|||x|x||||||X|
2|Desigualdades ante cancer colorectal|Felipe Quezada|Bruno Nervi|Raúl Aguilar|4|x|||x||||||X|
3|BioBancos en red|Alicia Colombo, Juan Carlos Roa|Enrique Castellon|Gerardo Donoso, Diego Romero|2,5|x|x||x|x|x|x||X|
3|Modelos preclinicos|Hector Contreras, Viviana Montecinos|Enrique Castellon|Patricia García, Carolina Bizama, Gareth Owen, Angel Castillo|2,4|x|x||x|x|x|x||Xx|
3|Biomarcadores e inmunoterapia|Mercedes López|Enrique Castellon|Bettina Müller, Roberto Estay||x|x||x|x|x|x||||
3|Biomarcadores geneticos|Katherine Marcelain|Enrique Castellon|Ricardo Armisen, Olga Barajas, Arnaldo Marín, Giuliano Bernal|2|x|x||x|x|x|x||x|
3|MicroRNAs predictivos|Jaime González|Enrique Castellon|Héctor Contreras, Guillermo Valenzuela||x||||||||x|
3|Marco regulatorio Terapias celulares|Viviana Montecinos|Bruno Nervi|Carolina Goic, Pablo Verdugo, Juan Alberto Lecaros, Gabriela Borin|2,3||||||||||
3|Ejercicio y cancer|Karol Ramirez|Enrique Castellon|Patricia Macanás|2|x|x||||||||x|
3|IA y mamografias|Susana Mondschein|Enrique Castellon|Nicolás Silva, Arnaldo Marín|2|||x|||||||x|
3|Microbiota|Erick Riquelme|Enrique Castellon|Arnoldo Riquelme|2|x||||||x|x|||x|
3|DPYD y toxicidad por FU|Olga Barajas|Enrique Castellon|Luis Quiñones, Leslie Cerpa, Claudio Alarcón|2||||||||||x|
3|Biomarcadores e inflamacion|Carolina Ibañez|Enrique Castellon|Mauricio Cuello|2||||||||||x|
4|Sociedad civil y PNC|Báltica Cabieses|Manuel Espinoza|Alexandra Obach, Antonia Roberts, Francisca Vezzani, Carla Campaña|||||||x||||X
4|Empoderammiento sociedad civil|Báltica Cabieses|Manuel Espinoza|Alexandra Obach, Antonia Roberts, Francisca Vezzani, Carla Campaña|1,2||||||||||X
4|Uso canastas GES|Paula Bedregal|Oscar Arteaga|Carolina de la Fuente, Paula Zamorano|2||||X||||||
4|Sistema de salud ante el cancer|Paula Bedregal|Oscar Arteaga|Pedro Zitko|1||||X||||||
4|Percepcion ante sistema de salud|Paula Bedregal|Oscar Arteaga|Victoria Lermanda, Mariol Luan, Camilo Oñate||||||||X||||X
4|Calidad y atencion|Paula Bedregal|Oscar Arteaga|Matías Libuy||||||X||||X
4|Oferta oncologos|Paula Bedregal|Oscar Arteaga|Constanza Roja, Bruno Nervi|2||||X||||||X
4|Modelos de atencion|Alejandra Fuentes|Oscar Arteaga|Verónica Kramer, Carla Flores, Alondra Castillo|1,2,3|X|X|X|X|X|X|X|X||X
5|App y navegacion|Carla Taramasco|Carla Taramasco|David Araya, Orietta Nicolis, Silvia Palma, Gaston Marquez|2|X|X|X|X|X|X|X|X||X
5|Datos para la accion|Carla Taramasco|Carla Taramasco|David Araya, Orietta Nicolis, Silvia Palma, Gaston Marquez|2|X|X|X|X|X|X|X|X|X|X
5|Sobrevida y ENS|Angélica Domínguez|Carla Taramasco|Paula Margozzini|||X|X||X|X|X|X||||
2|Formacion medica|Bruno Nervi|Bruno Nervi|Enrique Castellon, Carolina Goic, Pablo Verdugo||X|X|X|X|X|X|X|X||X
2|Formacion EPA|Francisca Marquez|Bruno Nervi|Enrique Castellon, Carolina Goic, Pablo Verdugo||X|X|X|X|X|X|X|X||X
2|Tamizaje cancer pulmonar|Angello Retamales|Bruno Nervi|Carolina Velasquez, Hector Galindo, Dsiego Carrillo, Paulo Olivera|1,3,5||||||||X||X|
2|Registro cancer Vesicula Biliar|Juan Carlos Araya|Bruno Nervi|Juan Carlos Roa|5||||||X|||||
"""

def normalize_name(name):
    if not name:
        return None
    return name.strip().replace('  ', ' ')

def extract_researchers_from_raw():
    researchers = set()
    reader = csv.DictReader(io.StringIO(RAW_DATA), delimiter='|')
    
    for row in reader:
        # Responsable
        resp = normalize_name(row.get('Investigador responsable'))
        if resp: researchers.add(resp)
        
        # Principales
        principales = row.get('Principales (8)')
        if principales:
            names = re.split(r',| y ', principales)
            for n in names:
                clean = normalize_name(n)
                if clean: researchers.add(clean)
                
        # Otros
        otros = row.get('Otros investigadores')
        if otros:
            names = re.split(r',| y ', otros)
            for n in names:
                clean = normalize_name(n)
                if clean: researchers.add(clean)
                
    return sorted(list(researchers))

def audit_database():
    print(f"--- Data Reconciliation Audit ---")
    print(f"Database: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print("ERROR: Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Check Tables
    print("\n[1] Checking Tables...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"Existing tables: {tables}")
    
    has_proyectos = 'proyectos' in tables or 'Proyectos' in tables
    has_investigadores = 'Investigadores' in tables or 'investigadores' in tables
    has_academic_members = 'academic_members' in tables
    
    print(f" - Table 'proyectos': {'YES' if has_proyectos else 'NO'}")
    print(f" - Table 'Investigadores' (Legacy): {'YES' if has_investigadores else 'NO'}")
    print(f" - Table 'academic_members' (New): {'YES' if has_academic_members else 'NO'}")
    
    # 2. Reconcile Researchers
    print("\n[2] Reconciling Researchers...")
    raw_researchers = extract_researchers_from_raw()
    print(f"Total unique researchers in RAW_DATA: {len(raw_researchers)}")
    
    db_researchers = set()
    if has_academic_members:
        cursor.execute("SELECT full_name FROM academic_members")
        db_researchers = {row[0] for row in cursor.fetchall() if row[0]}
    elif has_investigadores:
        cursor.execute("SELECT nombre FROM Investigadores")
        db_researchers = {row[0] for row in cursor.fetchall() if row[0]}
        
    print(f"Total researchers in DB: {len(db_researchers)}")
    
    matches = []
    gaps = []
    
    for name in raw_researchers:
        if name in db_researchers:
            matches.append(name)
        else:
            gaps.append(name)
            
    print(f" - Matches (Found in DB): {len(matches)}")
    print(f" - Gaps (Missing in DB): {len(gaps)}")
    
    if gaps:
        print("\n[!] Missing Researchers (First 10):")
        for g in gaps[:10]:
            print(f"   - {g}")
        if len(gaps) > 10:
            print(f"   ... and {len(gaps)-10} more.")
            
    conn.close()

if __name__ == "__main__":
    audit_database()
