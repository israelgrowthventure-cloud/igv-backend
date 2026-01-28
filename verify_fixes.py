#!/usr/bin/env python3
"""
Verify Fixes Script - IGV CRM
Created: 28 Janvier 2026
Vérifie que toutes les corrections sont appliquées
"""

import os
import re
import sys

# Couleurs ANSI pour le terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'

def check_file_exists(path):
    """Vérifie si un fichier existe"""
    return os.path.isfile(path)

def check_file_contains(path, pattern, is_regex=False):
    """Vérifie si un fichier contient un pattern"""
    if not os.path.isfile(path):
        return False
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if is_regex:
        return bool(re.search(pattern, content))
    return pattern in content

def check_file_not_contains(path, pattern):
    """Vérifie qu'un fichier NE contient PAS un pattern"""
    if not os.path.isfile(path):
        return True  # Le fichier n'existe pas, donc il ne contient pas le pattern
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    return pattern not in content

def print_result(check_name, passed, details=""):
    """Affiche le résultat d'une vérification"""
    status = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
    print(f"  {status} {check_name}")
    if details and not passed:
        print(f"      {YELLOW}→ {details}{RESET}")
    return passed

def main():
    print(f"\n{BOLD}🔍 IGV CRM - Vérification des corrections{RESET}\n")
    print("="*60)
    
    checks_passed = 0
    total_checks = 0
    
    # ========================
    # PHASE 1: SÉCURITÉ
    # ========================
    print(f"\n{BOLD}🔴 PHASE 1: SÉCURITÉ CRITIQUE{RESET}\n")
    
    # Check 1: Pas de password hardcodé
    total_checks += 1
    passed = check_file_not_contains(
        'server.py',
        'admin_password = "Admin@igv2025#"'
    )
    checks_passed += print_result(
        "server.py - Pas de password hardcodé",
        passed,
        'Ligne "admin_password = \\"Admin@igv2025#\\"" trouvée - SUPPRIMER'
    )
    
    # Check 2: Admin credentials from env
    total_checks += 1
    passed = check_file_contains(
        'server.py',
        "os.getenv('ADMIN_PASSWORD')"
    ) or check_file_contains(
        'server.py',
        'os.getenv("ADMIN_PASSWORD")'
    )
    checks_passed += print_result(
        "server.py - ADMIN_PASSWORD depuis env",
        passed,
        "Ajouter: admin_password = os.getenv('ADMIN_PASSWORD')"
    )
    
    # Check 3: cleanup_other_users commenté
    total_checks += 1
    passed = check_file_not_contains(
        'server.py',
        'await cleanup_other_users()'
    ) or check_file_contains(
        'server.py',
        '# await cleanup_other_users()'
    )
    checks_passed += print_result(
        "server.py - cleanup_other_users désactivé",
        passed,
        "Commenter: # await cleanup_other_users()"
    )
    
    # ========================
    # PHASE 2: ROUTES & ENDPOINTS
    # ========================
    print(f"\n{BOLD}🔴 PHASE 2: ROUTES & ENDPOINTS{RESET}\n")
    
    # Check 4: CRM router sans prefix
    total_checks += 1
    crm_main_path = os.path.join('app', 'routers', 'crm', 'main.py')
    passed = check_file_not_contains(
        crm_main_path,
        'router = APIRouter(prefix="/api/crm")'
    )
    checks_passed += print_result(
        f"{crm_main_path} - Pas de double prefix",
        passed,
        'Remplacer par: router = APIRouter()'
    )
    
    # Check 5: tasks_routes.py existe
    total_checks += 1
    passed = check_file_exists('tasks_routes.py')
    checks_passed += print_result(
        "tasks_routes.py existe",
        passed,
        "Copier tasks_routes.py depuis le package de corrections"
    )
    
    # Check 6: client_routes.py existe
    total_checks += 1
    passed = check_file_exists('client_routes.py')
    checks_passed += print_result(
        "client_routes.py existe",
        passed,
        "Copier client_routes.py depuis le package de corrections"
    )
    
    # Check 7: tasks_router importé dans server.py
    total_checks += 1
    passed = check_file_contains(
        'server.py',
        'from tasks_routes import'
    )
    checks_passed += print_result(
        "server.py - tasks_router importé",
        passed,
        "Ajouter: from tasks_routes import router as tasks_router"
    )
    
    # Check 8: client_router importé dans server.py
    total_checks += 1
    passed = check_file_contains(
        'server.py',
        'from client_routes import'
    )
    checks_passed += print_result(
        "server.py - client_router importé",
        passed,
        "Ajouter: from client_routes import router as client_router"
    )
    
    # ========================
    # PHASE 3: CONFIGURATION
    # ========================
    print(f"\n{BOLD}🔴 PHASE 3: CONFIGURATION{RESET}\n")
    
    # Check 9: .env.example existe
    total_checks += 1
    passed = check_file_exists('.env.example')
    checks_passed += print_result(
        ".env.example existe",
        passed,
        "Créer .env.example avec les variables requises"
    )
    
    # Check 10: .env existe
    total_checks += 1
    passed = check_file_exists('.env')
    checks_passed += print_result(
        ".env existe",
        passed,
        "Créer .env depuis .env.example et remplir les valeurs"
    )
    
    # Check 11: CORS depuis env (optionnel mais recommandé)
    total_checks += 1
    passed = check_file_contains(
        'server.py',
        "os.getenv('CORS_ORIGINS')"
    ) or check_file_contains(
        'server.py',
        'os.getenv("CORS_ORIGINS")'
    )
    checks_passed += print_result(
        "server.py - CORS_ORIGINS depuis env",
        passed,
        "Recommandé: Externaliser CORS vers variable d'environnement"
    )
    
    # ========================
    # RÉSUMÉ
    # ========================
    print("\n" + "="*60)
    print(f"{BOLD}SCORE: {checks_passed}/{total_checks} vérifications passées{RESET}")
    print("="*60)
    
    if checks_passed == total_checks:
        print(f"\n{GREEN}{BOLD}✅ TOUTES LES CORRECTIONS SONT APPLIQUÉES{RESET}\n")
        return 0
    elif checks_passed >= total_checks - 2:
        print(f"\n{YELLOW}{BOLD}⚠️ PRESQUE COMPLET - Quelques corrections manquantes{RESET}\n")
        return 1
    else:
        print(f"\n{RED}{BOLD}❌ CORRECTIONS INCOMPLÈTES - Voir les détails ci-dessus{RESET}\n")
        return 2

if __name__ == "__main__":
    sys.exit(main())
