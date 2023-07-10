# author Oleksander Kechedzhy
# version 1.0
#
__author__ = 'Oleksander Kechedzhy (alex.ithk@gmail.com)'
__version__ = '1.0'

import concurrent.futures as cf
import typing as tp
from os import cpu_count as cpu_count
from threading import Lock

from typing_extensions import Self

__all__ = ['TaskPoolCoroutine', 'TasksPool', 'TaskPoolCoroutineList']


class TaskPoolCoroutine:
    """
    The base class provides coroutines and data to execute computations asynchronously using threads in a pool
    without asyncio. It is needed to overload doTask(self, *argv, **kwargs) and doSaveResult(self).
    
    Args:
        index: int - index to be assigned to the object.
        on_run: bool - true (default) to sign the object as already in use for computation. This prevents using
            this object by class TasksPool to select next to run.
    """
    def __init__(self, index: int, on_run: bool = True):
        super().__init__()
        self.index: int = index
        self.onRun: bool = on_run
        self.result: tp.Any = ""
        self.lock: tp.Any = Lock()
    # }
    
    def __del__(self):
        """
        It calls from working thread.
        """
        self.onRun = False
    # }

    def set_on_run(self):
        """
        It calls from main thread. Do not need to lock.
        """
        self.lock.acquire(blocking=True, timeout=-1)
        self.onRun = True
    # }
    
    def set_off_run(self):
        self.lock.release()
        self.onRun = False
    # }
    
    # @abstractmethod
    def doTask(self, *argv, **kwargs) -> Self:
        """
        Coroutine in the context of the thread pool.
        
        Returns a self reference to TaskPoolCoroutine object.
        """
        ...

    def doSaveResult(self) -> tuple[int, int]:
        """
        Call in the context of the main thread to post-processing the result of coroutine doTask()
        saved in the TaskPoolCoroutine object.
        Returns integer as an abstract count of the finished anf fault job.
        """
        ...

# } TaskPoolCoroutine


class TaskPoolCoroutineList:
    """
    The base class provides the list of TaskPoolCoroutine objects. It is needed to overload createNew()
    or use appendTask() to add TaskPoolCoroutine objects to the list.
    """
    def __init__(self, max_size: int):
        super().__init__()
        self.index: int = 0
        self.max_size: int = max_size
        self.tasks_obj: list[TaskPoolCoroutine] = []
        
    # }

    def append(self, tasks_obj: TaskPoolCoroutine | None = None) -> TaskPoolCoroutine:
        """
        Append a new object to the TaskPoolCoroutine. In tasks_obj is None it will use createNew(index) on demand.
        
        Args:
            tasks_obj: TaskPoolCoroutine - object to add to the list or None (default). If None have been passed
                        TaskPoolCoroutine will be created by TaskPoolCoroutineList.createNew().
        
        Returns:
            TaskPoolCoroutine object from tasks_obj or created by calling TaskPoolCoroutineList.createNew()
        
        Raises:
            If the maximum number of objects in the list is achieved.
        """
        i = self.index
        if i == self.max_size:
            raise Exception("The maximum number of objects in the list is achieved!")
        # }
        if tasks_obj is None:
            tasks_obj = self.createNew(i)
        # }
        self.tasks_obj.append(tasks_obj)
        self.index += 1
        return tasks_obj
    # }
    
    def __getitem__(self, index: int) -> TaskPoolCoroutine:
        """
        Operator [] (TaskPoolCoroutineList[index]) to access TaskPoolCoroutine object in the list by index.
        
        Arg: 
            index: int - index of the element in the list counting from 0.
        
        Returns:
            TaskPoolCoroutine object.
        
        Raises:
            If the index is out of range!.
        """
        
        if index < 0 or index >= self.index:
            raise Exception("Index of the object TaskPoolCoroutine is out of range!")
        # }
        return self.tasks_obj[index]
    # }
        
    def getFreeSetRun(self) -> TaskPoolCoroutine | None:
        for t_obj in self.tasks_obj:
            if t_obj.lock.acquire(blocking=False):         # not t_obj.onRun
                t_obj.onRun = True
                return t_obj
            # }
        # }
        return None
    # }

    def createNew(self, index: int) -> TaskPoolCoroutine:
        """
        Create a new object inherited from TaskBoolCoroutine which represents a coroutine and its data for the
        thread pool.
        """
        return TaskPoolCoroutine(index)
    # }
    
    def getActiveCoroutineList(self) -> list[int]:
        """
        Returns the list of TaskPoolCoroutine objects with onRun==True.
        """
        return [t_obj.index for t_obj in self.tasks_obj if t_obj.onRun]
    # }

# }
    

class TasksPool:
    """
    An easy wrap of concurrent.futures.ThreadPoolExecutor() to execute computations asynchronously (tasks) associated
    with the object of class TaskPoolCoroutine, which presents the coroutine and its data.
    """
    def __init__(self, poll_size: int, coroutine_list: TaskPoolCoroutineList) -> None:
        self.coroutine_list: TaskPoolCoroutineList = coroutine_list
        self.poll_size: int = poll_size
        self.tasks_list: list = []
        self.next_index: int = 0
        self.totalDone: int = 0
        self.totalFault: int = 0
        self.currentIndex: int = 0

        # create pool
        if poll_size <= 0:
            max_workers = (cpu_count() or 2)
        else:
            max_workers = max(poll_size, (cpu_count() or 2))
        # }
        self.poolExecutor = cf.ThreadPoolExecutor(max_workers=max_workers)  # os.cpu_count()
    # }

    def __del__(self) -> None:
        if self.poolExecutor is not None:
            self.poolExecutor.shutdown()
        # }
    # }

    def submitTaskInPool(self, *argv, **kwargs) -> None:
        """
        Submit TaskPoolCoroutine.doTask(*argv, **kwargs) to execute on the thread pool.
        """
        if self.next_index < self.poll_size:
            tasks_obj = self.coroutine_list.append()
            tasks_obj.set_on_run()
            self.tasks_list.append(self.poolExecutor.submit(tasks_obj.doTask, *argv, **kwargs))
            self.next_index += 1
        else:
            total_done: int = 0
            task_index: int
            tasks_obj = self.coroutine_list.getFreeSetRun()
            if tasks_obj is None:
                task_index, total_done = self.waitForTasks(cf.FIRST_COMPLETED)
                tasks_obj = self.coroutine_list[task_index]
                tasks_obj.set_on_run()
            else:
                task_index = tasks_obj.index
            # }
            
            # tasks_obj.lock is already blocked here do not need to call tasks_obj.set_on_run()
            self.save_progress(total_done)
            self.tasks_list[task_index] = self.poolExecutor.submit(tasks_obj.doTask, *argv, **kwargs)
        # }

    # }

    def waitForAllTasks(self) -> int:
        _, total_done = self.waitForTasks(cf.ALL_COMPLETED)
        self.save_progress(total_done)
        return self.totalDone
    # }

    def waitForTasks(self, return_when: str) -> tuple[int, int]:
        # wait for any finished task
        free_task_index: int = -1
        total_done: int = 0
        total_fault: int = 0
        done: int
        fault: int
        tl = [self.tasks_list[i] for i in self.coroutine_list.getActiveCoroutineList()]
        finished, unfinished = cf.wait(tl, timeout=20, return_when=return_when)
        for t_obj in finished:
            task_result_obj: TaskPoolCoroutine = t_obj.result()
            if task_result_obj is None:
                raise Exception(f"A coroutine in the thread pool returns None object!")
            # }
            done, fault = task_result_obj.doSaveResult()
            total_done += done
            total_fault += fault
            free_task_index = task_result_obj.index
            task_result_obj.set_off_run()
        # }
        return free_task_index, total_done
    # }
    
    def save_progress(self, done: int, fault: int = 0) -> None:
        self.totalDone += done
        self.totalFault += fault
    # }

    def reset_progress(self, done: int = 0, fault: int = 0) -> None:
        self.totalDone = done
        self.totalFault = fault
    # }

# } TasksPool
