import asyncio
from functools import reduce
from typing import Text, Optional, List, Dict
import logging

from rasa.core.domain import Domain
from rasa.core.events import ActionExecuted, UserUttered, Event
from rasa.core.interpreter import RegexInterpreter, NaturalLanguageInterpreter
from rasa.core.training.structures import StoryGraph
from rasa.nlu.constants import MESSAGE_ACTION_NAME, MESSAGE_INTENT_NAME, ACTION_TEXT
from rasa.nlu.training_data import TrainingData, Message
from rasa.nlu.training_data import TrainingData
import rasa.utils.io as io_utils
import rasa.utils.common as common_utils

logger = logging.getLogger(__name__)


class TrainingDataImporter:
    """Common interface for different mechanisms to load training data."""

    async def get_domain(self) -> Domain:
        """Retrieves the domain of the bot.

        Returns:
            Loaded ``Domain``.
        """
        raise NotImplementedError()

    async def get_stories(
        self,
        interpreter: "NaturalLanguageInterpreter" = RegexInterpreter(),
        template_variables: Optional[Dict] = None,
        use_e2e: bool = False,
        exclusion_percentage: Optional[int] = None,
    ) -> StoryGraph:
        """Retrieves the stories that should be used for training.

        Args:
            interpreter: Interpreter that should be used to parse end to
                         end learning annotations.
            template_variables: Values of templates that should be replaced while
                                reading the story files.
            use_e2e: Specifies whether to parse end to end learning annotations.
            exclusion_percentage: Amount of training data that should be excluded.

        Returns:
            ``StoryGraph`` containing all loaded stories.
        """

        raise NotImplementedError()

    async def get_config(self) -> Dict:
        """Retrieves the configuration that should be used for the training.

        Returns:
            The configuration as dictionary.
        """

        raise NotImplementedError()

    async def get_nlu_data(self, language: Optional[Text] = "en") -> TrainingData:
        """Retrieves the NLU training data that should be used for training.

        Args:
            language: Can be used to only load training data for a certain language.

        Returns:
            Loaded NLU ``TrainingData``.
        """

        raise NotImplementedError()

    @staticmethod
    def load_from_config(
        config_path: Text,
        domain_path: Optional[Text] = None,
        training_data_paths: Optional[List[Text]] = None,
    ) -> "TrainingDataImporter":
        """Loads a ``TrainingDataImporter`` instance from a configuration file."""

        config = io_utils.read_config_file(config_path)
        return TrainingDataImporter.load_from_dict(
            config, config_path, domain_path, training_data_paths
        )

    @staticmethod
    def load_core_importer_from_config(
        config_path: Text,
        domain_path: Optional[Text] = None,
        training_data_paths: Optional[List[Text]] = None,
    ) -> "TrainingDataImporter":
        """Loads a ``TrainingDataImporter`` instance from a configuration file that
           only reads Core training data.
        """

        importer = TrainingDataImporter.load_from_config(
            config_path, domain_path, training_data_paths
        )

        return CoreDataImporter(importer)

    @staticmethod
    def load_nlu_importer_from_config(
        config_path: Text,
        domain_path: Optional[Text] = None,
        training_data_paths: Optional[List[Text]] = None,
    ) -> "TrainingDataImporter":
        """Loads a ``TrainingDataImporter`` instance from a configuration file that
           only reads NLU training data.
        """

        importer = TrainingDataImporter.load_from_config(
            config_path, domain_path, training_data_paths
        )

        return NluDataImporter(importer)

    @staticmethod
    def load_from_dict(
        config: Optional[Dict],
        config_path: Text,
        domain_path: Optional[Text] = None,
        training_data_paths: Optional[List[Text]] = None,
    ) -> "TrainingDataImporter":
        """Loads a ``TrainingDataImporter`` instance from a dictionary."""

        from rasa.importers.rasa import RasaFileImporter

        config = config or {}
        importers = config.get("importers", [])
        importers = [
            TrainingDataImporter._importer_from_dict(
                importer, config_path, domain_path, training_data_paths
            )
            for importer in importers
        ]
        importers = [importer for importer in importers if importer]

        if not importers:
            importers = [
                RasaFileImporter(config_path, domain_path, training_data_paths)
            ]

        return E2EImporter(CombinedDataImporter(importers))

    @staticmethod
    def _importer_from_dict(
        importer_config: Dict,
        config_path: Text,
        domain_path: Optional[Text] = None,
        training_data_paths: Optional[List[Text]] = None,
    ) -> Optional["TrainingDataImporter"]:
        from rasa.importers.multi_project import MultiProjectImporter
        from rasa.importers.rasa import RasaFileImporter

        module_path = importer_config.pop("name", None)
        if module_path == RasaFileImporter.__name__:
            importer_class = RasaFileImporter
        elif module_path == MultiProjectImporter.__name__:
            importer_class = MultiProjectImporter
        else:
            try:
                importer_class = common_utils.class_from_module_path(module_path)
            except (AttributeError, ImportError):
                logging.warning(f"Importer '{module_path}' not found.")
                return None

        constructor_arguments = common_utils.minimal_kwargs(
            importer_config, importer_class
        )
        return importer_class(
            config_path, domain_path, training_data_paths, **constructor_arguments
        )


class NluDataImporter(TrainingDataImporter):
    """Importer that skips any Core-related file reading."""

    def __init__(self, actual_importer: TrainingDataImporter):
        self._importer = actual_importer

    async def get_domain(self) -> Domain:
        return Domain.empty()

    async def get_stories(
        self,
        interpreter: "NaturalLanguageInterpreter" = RegexInterpreter(),
        template_variables: Optional[Dict] = None,
        use_e2e: bool = False,
        exclusion_percentage: Optional[int] = None,
    ) -> StoryGraph:
        return StoryGraph([])

    async def get_config(self) -> Dict:
        return await self._importer.get_config()

    async def get_nlu_data(self, language: Optional[Text] = "en") -> TrainingData:
        return await self._importer.get_nlu_data(language, only_nlu=True)


class CoreDataImporter(TrainingDataImporter):
    """Importer that skips any NLU related file reading."""

    def __init__(self, actual_importer: TrainingDataImporter):
        self._importer = actual_importer

    async def get_domain(self) -> Domain:
        return await self._importer.get_domain()

    async def get_stories(
        self,
        interpreter: "NaturalLanguageInterpreter" = RegexInterpreter(),
        template_variables: Optional[Dict] = None,
        use_e2e: bool = False,
        exclusion_percentage: Optional[int] = None,
    ) -> StoryGraph:
        return await self._importer.get_stories(
            interpreter, template_variables, use_e2e, exclusion_percentage, only_core=True,
        )

    async def get_config(self) -> Dict:
        return await self._importer.get_config()

    async def get_nlu_data(self, language: Optional[Text] = "en") -> TrainingData:
        return TrainingData()


class CombinedDataImporter(TrainingDataImporter):
    """A ``TrainingDataImporter`` that supports using multiple ``TrainingDataImporter``s as
        if they were a single instance.
    """

    def __init__(self, importers: List[TrainingDataImporter]):
        self._importers = importers

    async def get_config(self) -> Dict:
        configs = [importer.get_config() for importer in self._importers]
        configs = await asyncio.gather(*configs)

        return reduce(lambda merged, other: {**merged, **(other or {})}, configs, {})

    async def get_domain(self) -> Domain:
        domains = [importer.get_domain() for importer in self._importers]
        domains = await asyncio.gather(*domains)

        return reduce(
            lambda merged, other: merged.merge(other), domains, Domain.empty()
        )

    async def get_stories(
        self,
        interpreter: "NaturalLanguageInterpreter" = RegexInterpreter(),
        template_variables: Optional[Dict] = None,
        use_e2e: bool = False,
        exclusion_percentage: Optional[int] = None,
    ) -> StoryGraph:
        stories = [
            importer.get_stories(
                interpreter, template_variables, use_e2e, exclusion_percentage
            )
            for importer in self._importers
        ]
        stories = await asyncio.gather(*stories)

        return reduce(
            lambda merged, other: merged.merge(other), stories, StoryGraph([])
        )

    async def get_nlu_data(self, language: Optional[Text] = "en") -> TrainingData:
        nlu_data = [importer.get_nlu_data(language) for importer in self._importers]
        nlu_data = await asyncio.gather(*nlu_data)

        return reduce(
            lambda merged, other: merged.merge(other), nlu_data, TrainingData()
        )


class E2EImporter(TrainingDataImporter):
    """Importer which
    - enhances the NLU training data with actions / user messages from the stories.
    - adds potential end-to-end bot messages from stories as actions to the domain
    """

    def __init__(self, importer: TrainingDataImporter) -> None:
        self._importer = importer
        self._cached_stories: Optional[StoryGraph] = None

    async def get_domain(self) -> Domain:
        original, e2e_domain = await asyncio.gather(
            self._importer.get_domain(), self._get_domain_with_e2e_actions()
        )
        return original.merge(e2e_domain)

    async def _get_domain_with_e2e_actions(self) -> Domain:
        from rasa.core.events import ActionExecuted

        stories = await self.get_stories()

        additional_e2e_action_names = []
        for story_step in stories.story_steps:
            additional_e2e_action_names += [
                event.action_name
                for event in story_step.events
                if isinstance(event, ActionExecuted) and event.e2e_text
            ]

        additional_e2e_action_names = list(set(additional_e2e_action_names))

        return Domain(
            [], [], [], {}, action_names=additional_e2e_action_names, form_names=[]
        )

    async def get_stories(
        self,
        interpreter: "NaturalLanguageInterpreter" = RegexInterpreter(),
        template_variables: Optional[Dict] = None,
        use_e2e: bool = False,
        exclusion_percentage: Optional[int] = None,
    ) -> StoryGraph:
        if not self._cached_stories:
            # Simple cache to avoid loading all of this multiple times
            self._cached_stories = await self._importer.get_stories(
                interpreter, template_variables, use_e2e, exclusion_percentage
            )
        return self._cached_stories

    async def get_config(self) -> Dict:
        return await self._importer.get_config()

    async def get_nlu_data(self, language: Optional[Text] = "en", only_nlu: bool = False) -> TrainingData:
        training_datasets = [_additional_training_data_from_default_actions()]
        
        if only_nlu:
            training_datasets = await asyncio.gather(self._importer.get_nlu_data(language))
        else:
            training_datasets += await asyncio.gather(
            self._importer.get_nlu_data(language),
            self._additional_training_data_from_stories(),
        )


        return reduce(
            lambda merged, other: merged.merge(other), training_datasets, TrainingData()
        )

    async def _additional_training_data_from_stories(self) -> TrainingData:
        stories = await self.get_stories()

        additional_messages_from_stories = []
        for story_step in stories.story_steps:
            for event in story_step.events:
                message = _message_from_conversation_event(event)
                if message:
                    additional_messages_from_stories.append(message)

        logger.debug(
            f"Added {len(additional_messages_from_stories)} training data examples "
            f"from the story training data."
        )
        return TrainingData(additional_messages_from_stories)


def _message_from_conversation_event(event: Event) -> Optional[Message]:
    if isinstance(event, UserUttered):
        return _messages_from_user_utterance(event)
    elif isinstance(event, ActionExecuted):
        return _messages_from_action(event)

    return None


def _messages_from_user_utterance(event: UserUttered) -> Message:
    return Message(event.text, data={MESSAGE_INTENT_NAME: event.intent_name})


def _messages_from_action(event: ActionExecuted) -> Message:
    # we need to store the action text twice to be able to differentiate between user and bot text in NLU processing
    return Message(event.e2e_text or "", data={MESSAGE_ACTION_NAME: event.action_name, ACTION_TEXT: event.e2e_text or ""})


def _additional_training_data_from_default_actions() -> TrainingData:
    from rasa.nlu.training_data import Message
    from rasa.core.actions import action

    additional_messages_from_default_actions = [
        Message("", data={MESSAGE_ACTION_NAME: action_name})
        for action_name in action.default_action_names()
    ]

    return TrainingData(additional_messages_from_default_actions)
