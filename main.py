"""
Given an input file in CSV format representing a program to run, run the 
program and highlight the lines of code, generating a list of images.
"""


import sys 
from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm 


MILLISECONDS_PER_CYCLE = 200


def read_code_file(fname): 
    """
    Returns the list of code statements from the file. If there are any errors,
    print to the output each error in parsing, and exit the program. 
    """

    with open(fname, 'r') as f:
        first_line = next(f) 
    
        columns = [c.strip() for c in first_line.split('@')] 
        assert columns == ['pc', 'code', 'cyclecount', 'nextpc', 'meta'] 
        
        any_failed = False 
        data = [] 
        for index, line in enumerate(f): 
            line = line.split('@')
            try: 
                code = (
                    int(line[0]),  # pc (int)  <- Should be incrementing
                    str(line[1]),  # code (str)
                    int(line[2]),  # cyclecount (int)
                    str(line[3]),  # nextpc (Python code)
                    str(line[4].strip())   # meta (Python code) 
                )
                data.append(code)
            except Exception as ex: 
                print(f'Error while parsing line {index} of CSV')
                print(ex)
                print(f'  "{line}"')
                any_failed = True 
    
        if any_failed: 
            exit(1)

    # Confirm the data file is incrementing. 
    for index in range(1, len(data)): 
        assert data[index][0] == data[index-1][0] + 1,  \
            f'PCs should increment by 1 each line; error on "{data[index]}"'

    return data


def render(active_program, pc, cycle_count):
    """
    Renders the entire program. "PC" should be the line of code to highlight.
    The current cycle count is displayed. Returns a new PIL image representing 
    the rendered frame. 
    """

    STMT_PAD = 10  # Pixels to add between two statements

    # Find the expected image dimensions by counting (1) the valid lines of 
    # code, and (2) the longest line of code.
    font = ImageFont.truetype('data/FreeMono.ttf', 40)
    ascent, descent = font.getmetrics() 
    max_width, max_height = 0, 0
    active_lines = 0
    for code in active_program: 
        stmt = code[1]
        bbox = font.getmask(stmt).getbbox() 
        text_width, text_height = bbox[2], bbox[3] + descent
        max_width = max(max_width, text_width)
        max_height = max(max_height, text_height) 
        active_lines += 1 

    image_dimensions = (
        max_width + 40, 
        (active_lines + 1) * (max_height + STMT_PAD)
    )

    im = Image.new('RGB', image_dimensions, (255, 255, 255))
    ctx = ImageDraw.Draw(im)

    # Draw the code from the top-left downwards. Skip drawing the target line. 
    line_number = 0 
    target_idx, target_pos = -1, None 
    for index, line in enumerate(active_program):
        pos = (20, line_number * (max_height + STMT_PAD))
        if line[0] == pc: 
            target_idx = index 
            target_pos = pos
        else:
            ctx.text(pos, line[1], font=font, fill=(0, 0, 0))
        line_number += 1 
    
    # Draw the highlight and the target line. 
    if target_idx != -1: 
        ctx.rectangle(
            [
                (target_pos[0], target_pos[1] - 5), 
                (image_dimensions[0] - 20, target_pos[1] + max_height)
            ], 
            fill=(255, 255, 0)
        )
        ctx.text(
            target_pos, 
            active_program[target_idx][1],
            font=font, 
            fill=(0, 0, 0)
        )

    # In the bottom-right corner, write the cycle count.
    cycle_text = f'Cycles: {cycle_count}'
    text_pos = (
        image_dimensions[0] - 20, 
        line_number * (max_height + STMT_PAD)
    ) 
    ctx.text(text_pos, cycle_text, font=font, anchor='rt', fill=(0,0,0))

    return im 


def interpret(program, pc, state):
    """
    Returns the next PC and updates the program state. The current 
    instructions allowed for the "meta" field will be:
      `pass`: does nothing
      `assign name=expr`: evaluates the expression and adds it to state
      `exit`: represents the end of the program
    The "nextpc" field is an expression that can be evaluated to return an 
    integer value representing the next PC. 
    """

    # Get the code corresponding to the current PC.
    code = next(
        (line for line in program if line[0] == pc), 
        None
    ) 
    assert code is not None, f'Program is invalid! PC {pc} does not exist.'

    def local_eval(expr, state):
        """
        Evaluates the expression with respect to the local state.
        """
        statement = ""
        for key, value in state.items():
            assignment = f"(({key} := {value}) or True)"
            statement += assignment + " "
        if len(state) > 0:
            statement += "and "
        statement += f"({expr})"
        return eval(statement) 

    # Execute the meta field. 
    meta = code[4] 
    if meta == 'pass':
        # Do nothing special. 
        pass

    elif meta.startswith('assign'): 
        # Evaluate the expression and assign it a variable
        parts = meta.split()[1].split('=')
        name = parts[0].strip()
        expr = parts[1].strip()
        state[name] = local_eval(expr, state) 

    elif meta == 'exit':
        # Do nothing for now (TODO)
        pass 
    
    else:   
        exit(1, f'Error: unknown `meta` contents for PC {pc}: "{meta}"') 

    # Execute the "nextpc" field to get the next PC. 
    nextpc_field = code[3]
    result = local_eval(nextpc_field, state)

    return result 


if __name__ == '__main__':
    assert len(sys.argv) == 2, "An input program must be provided."
    program = read_code_file(sys.argv[1])
    
    # Lines which have no displayable code; these should not be added to the
    # trace. 
    meta_lines = {}  # set(int) of the PCs 
    active_program = [] 
    for code in program: 
        if code[1].strip() == '?':
            meta_lines.add(code[0]) 
        else:
            active_program.append(code) 

    state = {}
    pc = 1
    per_cycle_trace = [] 
    while pc != -1:
        pc = interpret(program, pc, state)
        if pc not in meta_lines and pc != -1:  
            # How many lines were we on the current line of code? 
            code = next((line for line in program if line[0] == pc))
            per_cycle_trace.extend([pc] * code[2])

    images = [] 
    for index, cycle in tqdm(enumerate(per_cycle_trace)): 
        im = render(active_program, cycle, index)
        images.append(im)
    
    images[0].save(
        'result.gif', 
        save_all=True, 
        append_images=images[1:],
        optimize=False, 
        duration=MILLISECONDS_PER_CYCLE, 
        loop=0
    )
