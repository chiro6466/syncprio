import logging
import time
import random
from typing import Dict, Any, List, Tuple, Callable

# 1. MOCKS Y CONSTANTES (Simulando su entorno)

# Configuración básica de logging para ver la salida
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('syncprio')
logger.setLevel(logging.DEBUG) # Nivel DEBUG para ver el Jitter/Defasaje

# Constantes de kernel.py (Simplificadas para la prueba)
MAX_EXECUTION_QUANTUM = 0.05
MAX_PENALTY_WEIGHT = 399
BASE_BACKOFF_TIME = 0.5
MAX_DELAY_CAP = 5.0 # Reducido para que la prueba corra rápido

ROLE_PRIORITY_MAP = {
    'ENGINE': 1, # Tier 1
    'RUNNER': 2, # Tier 2
    'LPT': 3     # Tier 3
}
ROLE_MAX_FAILS = {
    'ENGINE': 3, # Reducido a 3 fallos para ver el descarte rápido
    'RUNNER': 2, 
    'LPT': 1     
}

# Definición de la Tarea (8 elementos para Resiliencia)
Task = Tuple[int, int, int, str, Dict[str, Any], int, float, int]

# --- MOCK DECORADORES Y KERNEL (para que el script sea autocontenido) ---
def _inject_metadata(obj, key, role, global_tier, local_level):
    setattr(obj, '_kernel_role', role)
    setattr(obj, '_global_priority_tier', global_tier)
    setattr(obj, '_local_sequence_level', local_level)
    setattr(obj, '_logical_name', key)
    return obj

def engine(prio: int, key: str) -> Callable:
    def actual_decorator(obj: Any):
        return _inject_metadata(obj, key, 'ENGINE', ROLE_PRIORITY_MAP['ENGINE'], prio)
    return actual_decorator

def runner(prio: int, key: str) -> Callable:
    def actual_decorator(obj: Any):
        return _inject_metadata(obj, key, 'RUNNER', ROLE_PRIORITY_MAP['RUNNER'], prio)
    return actual_decorator

# La lógica del Kernel se ejecutará directamente sin la clase completa
# Para esta prueba, usaremos una lista simple como cola.
task_queue: List[Task] = []
is_running = True
execution_counter = 0

def _calculate_weight(global_tier: int, local_level: int) -> int:
    return (global_tier * 100) + local_level


# 2. TAREAS DE FALLA INTENCIONAL (La Inyección de Fallas)

# Contador para forzar la detención de la prueba
MAX_TOTAL_EXECUTION_TIME = 15 

# Tarea de Autenticación Crítica (ENGINE)
@engine(prio=10, key="API_AUTH")
def api_auth_task():
    global execution_counter
    execution_counter += 1
    # Forzamos una excepción IMMEDIATA
    if execution_counter < 10: # Falla 10 veces para darle tiempo a fallar y reencolar
        raise ConnectionError("API externa no responde. Falla Forzada.")
    
# Tarea de Lógica de Negocio (RUNNER)
@runner(prio=50, key="BUSINESS_LOGIC")
def logic_task():
    global execution_counter
    execution_counter += 1
    # Falla 5 veces
    if execution_counter < 5: 
        raise TimeoutError("Lógica de Negocio falló por tiempo de espera.")

# 3. SETUP Y EJECUCIÓN (Usando la lógica de add_task y run_loop)

def setup_task(task_obj):
    # Lógica simplificada de add_task
    role = getattr(task_obj, '_kernel_role')
    global_tier = getattr(task_obj, '_global_priority_tier')
    local_level = getattr(task_obj, '_local_sequence_level')
    logical_name = getattr(task_obj, '_logical_name')
    
    weight = _calculate_weight(global_tier, local_level)

    # Inicialización de Resiliencia
    fail_count = 0
    unblock_time = 0.0
    weight_original = weight 
    
    new_task: Task = (
        weight, global_tier, local_level, logical_name, {},
        fail_count, unblock_time, weight_original
    )
    task_queue.append(new_task)
    task_queue.sort(key=lambda x: x[0])
    logger.info(f"SETUP: Tarea '{logical_name}' ({role}) añadida. Weight: {weight}")


def run_test_loop():
    start_test_time = time.time()
    
    # Simulación del loop de kernel.py
    while (time.time() - start_test_time) < MAX_TOTAL_EXECUTION_TIME:
        if not task_queue:
            time.sleep(0.01) 
            continue
            
        # Extracción y Desempaquetamiento (8 elementos)
        (weight, global_tier, local_level, logical_name, args, 
         fail_count, unblock_time, weight_original) = task_queue.pop(0)
        
        role = next(k for k, v in ROLE_PRIORITY_MAP.items() if v == global_tier)

        # --- CHECK DE DEFAZAJE (JITTER) ---
        if unblock_time > time.time():
            # La tarea está en backoff. Reencolar y saltar la ejecución.
            logger.debug(f" [TASK DELAY] -> Role: {role}, Name: {logical_name} esperando backoff ({unblock_time - time.time():.2f}s restantes).")
            
            task_queue.append((
                weight, global_tier, local_level, logical_name, args, 
                fail_count, unblock_time, weight_original
            ))
            task_queue.sort(key=lambda x: x[0])
            time.sleep(0.001)
            continue
        
        # --- EJECUCIÓN ---
        try:
            task_func = globals()[logical_name] # Simula la resolución
            logger.info(f" [TASK EXEC] -> Ejecutando Role: {role}, Name: {logical_name}. Intento # {fail_count + 1}")
            task_func()
            
        except Exception as e:
            # LÓGICA DE FALLO Y BACKOFF CON JITTER
            max_fails = ROLE_MAX_FAILS.get(role, 1)
            fail_count += 1
            
            if fail_count >= max_fails:
                logger.critical(f" [TASK FATAL] 🚨 Role: {role}, Name: {logical_name} falló {fail_count} veces. DESCARTE PERMANENTE.")
                continue # Descartar tarea

            # Cálculo de Jitter
            exponential_delay = BASE_BACKOFF_TIME * (2 ** fail_count)
            delay = min(random.uniform(0, exponential_delay), MAX_DELAY_CAP) # Jitter
            unblock_time = time.time() + delay
            
            # Penalización: Prioridad Degradada
            weight_new = MAX_PENALTY_WEIGHT 
            
            logger.error(f" [TASK FAIL] -> Role: {role}, Name: {logical_name} falló: {e}. Reencolando con {delay:.2f}s de Jitter (Weight: {weight_new}).")
            
            # Reencolar con el nuevo estado penalizado
            task_queue.append((
                weight_new, global_tier, local_level, logical_name, args, 
                fail_count, unblock_time, weight_original
            ))
            task_queue.sort(key=lambda x: x[0])
            continue

        # --- LÓGICA DE ÉXITO (Restauración) ---
        if role in ['ENGINE', 'RUNNER', 'LPT']:
            
            # Restauración de Prioridad (si la tarea falla y luego tiene éxito, el weight se restaura)
            weight_restored = weight_original
            fail_count_reset = 0
            unblock_time_reset = 0.0
            
            # Reencolar con los valores restaurados
            task_queue.append((
                weight_restored, global_tier, local_level, logical_name, args, 
                fail_count_reset, unblock_time_reset, weight_original
            ))
            task_queue.sort(key=lambda x: x[0])
        
        time.sleep(0.001)

    logger.info("TEST TERMINADO: Fin del tiempo de simulación.")

# --- INICIO DEL TEST ---
if __name__ == '__main__':
    setup_task(api_auth_task)
    setup_task(logic_task)
    logger.info("Cola inicial (ordenada por prioridad): " + str([t[3] for t in task_queue]))
    
    run_test_loop()