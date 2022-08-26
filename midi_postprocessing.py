"""
This script handles the post-processing of the midi generated from the
Music Transformer. This include converting possible polyphonic melody to 
monophonic, and fit the melody to the acceptable range as input for MLP Singer.

Furthermore, when specified, it can perform time-stretching, and remove
seed melody from generated files
"""

import math
import random
import logging
import os
import pretty_midi
  
def select_note_from_group(group, logic_type):
  """
  Given a group of notes, it selects one based on the defined logic type.
  It can work in three ways:
  logic_type = 0
    In this mode, the lowest pitch in a chord is always selected
  logic type = 1
    In this mode, the middle pitch in a chord is always selected. If there is
    no clear middle item, a random choice between the two most central ones
    is made
  logic_type = 2
    In this mode, the highest pitch in a chord is always selected
  
  Parameters
  ----------
  group : list
      A list with notes, generated by the midi_postprocessing function
  logic_type : int
      The algorithm used to convert from polyphonic to monophonic

  Returns
  -------
  list
      The selected note
  """
  assert logic_type >= 0 and logic_type <= 2, 'The provided logic type is invalid'

  selected_idx = -1

  if logic_type == 0: # select min index
    selected_idx = 0
  elif logic_type == 1: # select middle index (if possible)
    middle = float(len(group)) / 2 
    if middle % 2 == 0 or len(group) == 2: # if there's a doubt, select a random one
      possible_items = [int(middle), int(middle-1)]
      selected_idx = random.choice(possible_items)
    else: # if there's a clear middle item, select it
      selected_idx = int(middle - .5)
  elif logic_type == 2: # select max index
    selected_idx = len(group) - 1

  selected_note = group[selected_idx]
  logging.info(f'Polyphony to monophony - selected note: {selected_note} among {group}')

  return selected_note

def fit_to_pitch_range(note, range_min, range_max):
  """
  Given a note as input, it transpose it up and down the required amount of 
  octaves to fit a lower and upper boundary range

  Parameters
  ----------
  note : list
      A note attribute list, generated from the midi_postprocessing function
  range_min : int
      The minimum possible range for the melody (in midi pitch)
  range_max : int
      The maximum possible range for the melody (in midi pitch)

  Returns
  -------
  list
      The transposed note
  """
  pitch = note[2]

  if pitch > range_max:
    octaves_to_transpose = (pitch-range_max) / 12
    octaves_to_transpose = int(math.ceil(octaves_to_transpose))
    
    logging.info(f'Transpose down - Pitch: {pitch} - Transpose {octaves_to_transpose} octave(s)')
    note[2] = pitch - (12 * octaves_to_transpose)
  elif pitch < range_min:
    octaves_to_transpose = (range_min-pitch) / 12
    octaves_to_transpose = int(math.ceil(octaves_to_transpose))

    logging.info(f'Transpose up - Pitch: {pitch} - Transpose {octaves_to_transpose} octave(s)')
    note[2] = pitch + (12 * octaves_to_transpose)
  
  return note


def midi_postprocessing(input_midi_file,
                        output_midi_file,
                        melody_seed_file,
                        global_var,
                        time_multiplier = 1,
                        logic_type = 1,
                        add_legato = True):
  """
  This function runs all the midi post processing steps.
  Given an input midi file (generated by Music Transformer), it ensures that
  polyphony is converted to monophony, and that the pitches are within the
  allowed range

  Furthermore, it can perform time-stretching and it removes the seed of a 
  generated melody

  Parameters
  ----------
  input_midi_file : str
      The generated melody in form of path to midi file 
  output_midi_file : str
      The path to the output post-processed midi
  melody_seed_file : str
      The path to the melody seed midi file
  global_var : dict
      The dictionary containing the global variables 
  time_multiplier : int (optional, default: 1)
      The multiplier to perform time stretching
      A value of 2, for example, will have all the note durations to be twice 
      as long
  logic_type : int (optional, default: 1)
      Logic for the polyphony to monophony algorithm
  add_legato : bool (optional, default: True)
      If true, adds legato to all the notes in the post-processed midi

  Returns
  -------
  int
      The number of pitches in the generated melody 
  """

  range_min = global_var['melody_lower_boundary']
  range_max = global_var['melody_upper_boundary']

  # read midi input file
  midi_data = pretty_midi.PrettyMIDI(input_midi_file)
  midi_list = []

  for instrument in midi_data.instruments:
    for note in instrument.notes:
      # apply time multiplier
      start = note.start * time_multiplier
      end = note.end * time_multiplier
      pitch = note.pitch
      midi_list.append([start, end, pitch])

  logging.info(f'Applied time multiplier: {time_multiplier}')
  
  # sort asc by start time, and by pitch
  midi_list = sorted(midi_list, key=lambda x: (x[0], x[2]))

  # group by start time
  values = sorted(set(map(lambda x:x[0], midi_list)))
  group_by_start_time = [[y for y in midi_list if y[0]==x] for x in values]

  selected_notes = []

  for group in group_by_start_time:
    # select note from group based on the logic, if there is polyphony
    if len(group) > 1:
      note = select_note_from_group(group, logic_type)
    else:
      note = group[0]

    # fit pitch to range
    note = fit_to_pitch_range(note, range_min, range_max)

    # check if it is possible to add to selected_notes list
    add = False

    if len(selected_notes) > 0:
      note_start_time = note[0]
      previous_group_end_time = selected_notes[-1][1]

      if note_start_time >= previous_group_end_time: # ensure no notes overlap
        if add_legato: # set previous note end time as current note start time
          selected_notes[-1][1] = note_start_time

        add = True
    else:
      add = True
    
    if add:
      selected_notes.append(note)
  
  # write post-processed midi file out
  out_midi = pretty_midi.PrettyMIDI()
  
  piano_program = pretty_midi.instrument_name_to_program('Acoustic grand piano')
  piano = pretty_midi.Instrument(program=piano_program)
  
  for note in selected_notes:
    pretty_midi_note = pretty_midi.Note(velocity=127, pitch=note[2], start=note[0], end=note[1])
    piano.notes.append(pretty_midi_note)

  out_midi.instruments.append(piano)

  out_midi_path = output_midi_file
  out_midi.write(out_midi_path)

  logging.info(f'Wrote postprocessed .mid to: {out_midi_path}')

  pitches_count = len(selected_notes)
  return pitches_count