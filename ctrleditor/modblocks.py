from dataclasses import dataclass, field
from typing import Dict, List
import ipywidgets as widgets
from IPython.display import display, clear_output
import json
from datetime import datetime 
from pharmpy.model import Model
from pathlib import Path

@dataclass
class ChangeLogEntry:
    timestamp: str
    block_name: str
    orginal_content: List[str]
    updated_content: List[str]


@dataclass
class ModelBlocks:
    blocks: Dict[str, List[List[str]]] = field(default_factory=dict)
    change_log: List[ChangeLogEntry] = field(default_factory=list)
    
    def add_block(self, block_name: str, block_content: List[str]):
        if block_name not in self.blocks:
            self.blocks[block_name] = []
        self.blocks[block_name].append(block_content)
    
    def update_block(self, block_name: str, new_content: List[str]):
        if block_name in self.blocks:
            orig_content = self.blocks[block_name]
            self.blocks[block_name] = [new_content]
            self.log_change(block_name, orig_content, new_content)
        else:
            raise ValueError(f"Block '{block_name}' not found in model.")
    
    def log_change(self, block_name: str, original_content: List[str], updated_content: List[str]):
        entry = ChangeLogEntry(
            timestamp=datetime.now().isoformat(),
            block_name=block_name,
            orginal_content=original_content,
            updated_content=updated_content
        )
        self.change_log.append(entry)
        
    def save_change_log(self, name, path: str):
        path = Path(path)
        self._check_path(path)
        file_path = path / f"{name}_log.json"
        
        with file_path.open("w", encoding="utf-8") as file:
            json.dump([entry.__dict__ for entry in self.change_log], file, indent=4)
        print(f"Change log saved to '{file_path}'.")
        
    def save_model(self, name: str, path: str = "."):
        path = Path(path)
        self._check_path(path)
        file_path = path / f"{name}.ctl"
        
        with file_path.open("w", encoding="utf-8") as file:
            file.write(self.render())
        print(f"Model saved to '{file_path}'.")
        
    def save(self, name: str, path: str = "."):
        self.save_model(name, path)
        self.save_change_log(name, path)
            
    def render(self) -> str:
        sections = []
        for block_name, contents in self.blocks.items():
            for content in contents:
                sections.extend(content)
            sections.append("\n")
        return "".join(sections).strip()
    
    def copy(self):
        return ModelBlocks(
            blocks={key: [list(content) for content in value] for key, value in self.blocks.items()},
            change_log=list(self.change_log)
        )
    
    def _check_path(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)

    
def parse_control_file(file_path: str) -> ModelBlocks:
    
    with open(file_path, "r") as file:
        lines = file.readlines()
    
    model_blocks = _parse_lines(lines)
    
    return model_blocks


def _parse_lines(lines):
    model_blocks = ModelBlocks()
    
    current_block = None
    block_content = []
    for line in lines:
        if line.strip().startswith("$"):
            if current_block:
                model_blocks.add_block(current_block, block_content)
            current_block = line.strip().split()[0]
            block_content = [line]
        elif current_block:
            block_content.append(line)
        else:
            continue
    if current_block:
        model_blocks.add_block(current_block, block_content)
    
    return model_blocks


def widget_edit_block(block_content: List[str], save_callback=None):
    flattened_block_content = [item for sublist in block_content for item in sublist]
    original_text = "".join(flattened_block_content)
    
    orig_textarea = widgets.Textarea(
        value=original_text,
        placeholder="Original block content...",
        layout=widgets.Layout(width="48%", height="150px", margin="0 1% 0 0"),
        disabled=True
    )
    
    edit_textarea = widgets.Textarea(
        value=original_text,
        placeholder="Edit block content here...",
        layout=widgets.Layout(width="48%", height="150px", margin="0 0 0 1%")
    )
    
    save_button = widgets.Button(description="Save", button_style="success")
    output = widgets.Output()
    
    def on_save_clicked(_):
        updated_content = edit_textarea.value
        with output:
            clear_output(wait=True)
            print("Changes saved!")
        if save_callback:
            save_callback(updated_content)
    
    save_button.on_click(on_save_clicked)
    display(widgets.VBox([
        widgets.HBox([orig_textarea, edit_textarea]),
        save_button, 
        output
        ]))


def edit_model_blocks(model_blocks: ModelBlocks, block_names: List[str]):
    updated_model_blocks = model_blocks.copy()
    
    for block_name in block_names:
        if block_name not in model_blocks.blocks:
            raise ValueError(f"Block '{block_name}' not found in model.")
        
        block_content = model_blocks.blocks[block_name]
        
        def save_callback(updated_content, block_name=block_name):
            updated_model_blocks.update_block(block_name, updated_content.splitlines(keepends=True))
            print(f"Block '{block_name}' updated.")
        
        widget_edit_block(block_content, save_callback=save_callback)
    
    return updated_model_blocks


def replay_changes(model_blocks: ModelBlocks, change_log_file: str):
    updated_model_blocks = model_blocks.copy()
    
    with open(change_log_file, "r") as file:
        change_log = json.load(file)
    
    for entry in change_log:
        updated_model_blocks.update_block(entry["block_name"], entry["updated_content"])
        print(f"Block '{entry['block_name']}' updated at {entry['timestamp']}")
    print("All changes replayed successfully.")
    
    return updated_model_blocks


def pharmpy_to_blocks(model: Model) -> ModelBlocks:
    # NOTE: we assume model has been converted to nonmem format here
    model_code = model.code
    lines = model_code.splitlines(keepends=True)
    model_blocks = _parse_lines(lines)
    
    return model_blocks


def blocks_to_pharmpy(model_blocks: ModelBlocks, parent_model: Model, path: str = None) -> Model:
    model_code = model_blocks.render()
    model = parent_model.parse_model_from_string(model_code)
    model = model.replace(
        dataset=parent_model.dataset,
        datainfo=parent_model.datainfo,
    )
    
    if path:
        model_blocks.save_change_log(path)
        
    return model