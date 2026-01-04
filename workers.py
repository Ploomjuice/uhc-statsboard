from team_builder_simulator import Simulator
from db_update import Loader
from PySide6.QtCore import Slot, Signal, QObject

class UpdateWorker(QObject):
    finished = Signal()
    progress = Signal(str)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    @Slot()
    def run(self):
        try:
            loader = Loader()
            to_add, msg = loader.refresh()

            if to_add:
                self.error.emit(msg)
            else:
                self.progress.emit(msg)
            # FullAggregation(update=True)


        except Exception as e:
            self.error.emit(str(e))
        else:
            self.finished.emit()


class SimulatorWorker(QObject):
    finished = Signal()
    progress = Signal(str)
    error = Signal(str)
    test_round = Signal(list)
    agg_stats = Signal(dict)

    def __init__(self, table_dict, parent=None, iter=1):
        super().__init__(parent)
        self.n_sims = iter
        self.table_dict = table_dict


    @Slot()
    def run(self):
        try:
            simulator = Simulator(self.table_dict)

            simulator.simulate(self.n_sims)


            random_round = simulator.get_random_simulation()
            results = simulator.aggregate_sims()


            self.test_round.emit(random_round)
            self.agg_stats.emit(results)


        except Exception as e:
            self.error.emit(str(e))
            return
        else:
            self.finished.emit()