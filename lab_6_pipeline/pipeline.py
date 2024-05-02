"""
Pipeline for CONLL-U formatting.
"""
# pylint: disable=too-few-public-methods, unused-import, undefined-variable, too-many-nested-blocks
import pathlib
import spacy_udpipe

from networkx import DiGraph

from core_utils.article.article import (Article, ArtifactType, get_article_id_from_filepath,
                                        split_by_sentence)
from core_utils.article.io import from_meta, from_raw, to_cleaned
from core_utils.constants import ASSETS_PATH, UDPIPE_MODEL_PATH
from core_utils.pipeline import (AbstractCoNLLUAnalyzer, CoNLLUDocument, LibraryWrapper,
                                 PipelineProtocol, StanzaDocument, TreeNode)


class InconsistentDatasetError(Exception):
    """
    IDs contain slips, number of meta and raw files is not equal, files are empty.
    """


class EmptyDirectoryError(Exception):
    """
    Directory is empty.
    """


class EmptyFileError(Exception):
    """
    File is empty.
    """


class CorpusManager:
    """
    Work with articles and store them.
    """

    def __init__(self, path_to_raw_txt_data: pathlib.Path) -> None:
        """
        Initialize an instance of the CorpusManager class.

        Args:
            path_to_raw_txt_data (pathlib.Path): Path to raw txt data
        """
        self.path_to_raw_txt_data = path_to_raw_txt_data
        self._storage = {}

        self._validate_dataset()
        self._scan_dataset()

    def _validate_dataset(self) -> None:
        """
        Validate folder with assets.
        """
        if not self.path_to_raw_txt_data.exists():
            raise FileNotFoundError  # built-in

        if not self.path_to_raw_txt_data.is_dir():
            raise NotADirectoryError  # built-in

        if not any(self.path_to_raw_txt_data.iterdir()):
            raise EmptyDirectoryError

        metas = list(self.path_to_raw_txt_data.glob('*_meta.json'))
        raws = list(self.path_to_raw_txt_data.glob('*_raw.txt'))
        if len(metas) != len(raws):
            raise InconsistentDatasetError

        metas.sort(key=lambda x: int(get_article_id_from_filepath(x)))
        raws.sort(key=lambda x: int(get_article_id_from_filepath(x)))

        for index, (meta, raw) in enumerate(zip(metas, raws)):
            if index + 1 != get_article_id_from_filepath(meta) \
                    or index + 1 != get_article_id_from_filepath(raw)\
                    or meta.stat().st_size == 0 or raw.stat().st_size == 0:
                raise InconsistentDatasetError

    def _scan_dataset(self) -> None:
        """
        Register each dataset entry.
        """
        self._storage = {
            get_article_id_from_filepath(file):
            from_raw(
                path=file,
                article=Article(url=None,
                                article_id=get_article_id_from_filepath(file))
            )
            for file in self.path_to_raw_txt_data.glob('*_raw.txt')
        }

    def get_articles(self) -> dict:
        """
        Get storage params.

        Returns:
            dict: Storage params
        """
        return self._storage


class TextProcessingPipeline(PipelineProtocol):
    """
    Preprocess and morphologically annotate sentences into the CONLL-U format.
    """

    def __init__(
        self, corpus_manager: CorpusManager, analyzer: LibraryWrapper | None = None
    ) -> None:
        """
        Initialize an instance of the TextProcessingPipeline class.

        Args:
            corpus_manager (CorpusManager): CorpusManager instance
            analyzer (LibraryWrapper | None): Analyzer instance
        """
        self._corpus = corpus_manager
        self.analyzer = analyzer

    def run(self) -> None:
        """
        Perform basic preprocessing and write processed text to files.
        """
        for article in self._corpus.get_articles().values():
            from_meta(article.get_meta_file_path(), article)
            from_raw(article.get_raw_text_path(), article)
            to_cleaned(article)
            if self.analyzer:
                article.set_conllu_info(self.analyzer.analyze(split_by_sentence(article.text)))
                self.analyzer.to_conllu(article)


class UDPipeAnalyzer(LibraryWrapper):
    """
    Wrapper for udpipe library.
    """

    _analyzer: AbstractCoNLLUAnalyzer

    def __init__(self) -> None:
        """
        Initialize an instance of the UDPipeAnalyzer class.
        """
        self._analyzer = self._bootstrap()

    def _bootstrap(self) -> AbstractCoNLLUAnalyzer:
        """
        Load and set up the UDPipe model.

        Returns:
            AbstractCoNLLUAnalyzer: Analyzer instance
        """
        return spacy_udpipe.load_from_path(lang="ru", path=str(UDPIPE_MODEL_PATH))

    def analyze(self, texts: list[str]) -> list[StanzaDocument | str]:
        """
        Process texts into CoNLL-U formatted markup.

        Args:
            texts (list[str]): Collection of texts

        Returns:
            list[StanzaDocument | str]: List of documents
        """
        sentences = []

        for num, text in enumerate(texts):
            sentence = ['	'.join([str(token.i + 1),
                                  token.text,
                                  token.lemma_,
                                  token.pos_,
                                  '_',
                                  str(token.morph) if token.morph else '_',
                                  '0' if token.dep_ == 'ROOT' else str(token.head.i + 1),
                                  token.dep_,
                                  '_',
                                  'SpaceAfter=No' if not token.whitespace_ else '_'])
                        for token in self._analyzer(text)]

            sentences.append(f"# sent_id = {num + 1}\n"
                             f"# text = {text}\n" +
                             "\n".join(sentence + ['', '']))
        return sentences

    def to_conllu(self, article: Article) -> None:
        """
        Save content to ConLLU format.

        Args:
            article (Article): Article containing information to save
        """
        with open(article.get_file_path(kind=ArtifactType.UDPIPE_CONLLU),
                  'w', encoding='utf-8') as f:
            con = article.get_conllu_info()
            f.writelines(con)


class StanzaAnalyzer(LibraryWrapper):
    """
    Wrapper for stanza library.
    """

    _analyzer: AbstractCoNLLUAnalyzer

    def __init__(self) -> None:
        """
        Initialize an instance of the StanzaAnalyzer class.
        """

    def _bootstrap(self) -> AbstractCoNLLUAnalyzer:
        """
        Load and set up the Stanza model.

        Returns:
            AbstractCoNLLUAnalyzer: Analyzer instance
        """

    def analyze(self, texts: list[str]) -> list[StanzaDocument]:
        """
        Process texts into CoNLL-U formatted markup.

        Args:
            texts (list[str]): Collection of texts

        Returns:
            list[StanzaDocument]: List of documents
        """

    def to_conllu(self, article: Article) -> None:
        """
        Save content to ConLLU format.

        Args:
            article (Article): Article containing information to save
        """

    def from_conllu(self, article: Article) -> CoNLLUDocument:
        """
        Load ConLLU content from article stored on disk.

        Args:
            article (Article): Article to load

        Returns:
            CoNLLUDocument: Document ready for parsing
        """


class POSFrequencyPipeline:
    """
    Count frequencies of each POS in articles, update meta info and produce graphic report.
    """

    def __init__(self, ucorpus_manager: CorpusManager, analyzer: LibraryWrapper) -> None:
        """
        Initialize an instance of the POSFrequencyPipeline class.

        Args:
            corpus_manager (CorpusManager): CorpusManager instance
            analyzer (LibraryWrapper): Analyzer instance
        """

    def run(self) -> None:
        """
        Visualize the frequencies of each part of speech.
        """

    def _count_frequencies(self, article: Article) -> dict[str, int]:
        """
        Count POS frequency in Article.

        Args:
            article (Article): Article instance

        Returns:
            dict[str, int]: POS frequencies
        """


class PatternSearchPipeline(PipelineProtocol):
    """
    Search for the required syntactic pattern.
    """

    def __init__(
        self, corpus_manager: CorpusManager, analyzer: LibraryWrapper, pos: tuple[str, ...]
    ) -> None:
        """
        Initialize an instance of the PatternSearchPipeline class.

        Args:
            corpus_manager (CorpusManager): CorpusManager instance
            analyzer (LibraryWrapper): Analyzer instance
            pos (tuple[str, ...]): Root, Dependency, Child part of speech
        """

    def _make_graphs(self, doc: CoNLLUDocument) -> list[DiGraph]:
        """
        Make graphs for a document.

        Args:
            doc (CoNLLUDocument): Document for patterns searching

        Returns:
            list[DiGraph]: Graphs for the sentences in the document
        """

    def _add_children(
        self, graph: DiGraph, subgraph_to_graph: dict, node_id: int, tree_node: TreeNode
    ) -> None:
        """
        Add children to TreeNode.

        Args:
            graph (DiGraph): Sentence graph to search for a pattern
            subgraph_to_graph (dict): Matched subgraph
            node_id (int): ID of root node of the match
            tree_node (TreeNode): Root node of the match
        """

    def _find_pattern(self, doc_graphs: list) -> dict[int, list[TreeNode]]:
        """
        Search for the required pattern.

        Args:
            doc_graphs (list): A list of graphs for the document

        Returns:
            dict[int, list[TreeNode]]: A dictionary with pattern matches
        """

    def run(self) -> None:
        """
        Search for a pattern in documents and writes found information to JSON file.
        """


def main() -> None:
    """
    Entrypoint for pipeline module.
    """
    corpus_manager = CorpusManager(path_to_raw_txt_data=ASSETS_PATH)
    udpipe_analyzer = UDPipeAnalyzer()
    pipeline = TextProcessingPipeline(corpus_manager, udpipe_analyzer)
    pipeline.run()


if __name__ == "__main__":
    main()
